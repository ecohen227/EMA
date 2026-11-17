"""The evoked analysis: measure the recordings of every folder in an ROI file with a protocol.

Everything about an analysis is kept in one file in its output folder,
`evoked_analysis.json` (see ema.kept_results). A new run measures only what is
new: folders that were not measured before, and folders whose ROI, electrode,
flags or recordings changed. Every other folder keeps its results, including
folders of an earlier ROI file. With another protocol everything is measured
again. The two Excel files are then written from the kept results (see
ema.evoked.workbook).

Nothing here needs the GUI::

    from ema.evoked.analysis import Analysis, run
    from ema.evoked.protocol import Protocol
    from ema.evoked.workbook import write_workbooks
    from ema.roi_selection import Selections

    analysis = Analysis.open("my output folder")
    run(analysis, Protocol.load("my protocol.json"), Selections.load("roi_selections.json"))
    analysis.save()
    write_workbooks(analysis)
"""

from functools import lru_cache
from pathlib import Path

from ..kept_results import FolderResult, KeptAnalysis, Plan, RecordingResult, fingerprint, now, why_not_measured
from ..recordings import list_recordings, load_stack
from .measures import measure, summarise
from .protocol import EVERY, Protocol
from .spatial import measure_spatial
from .traces import find_partner, make_movie, make_trace

FILE_NAME = "evoked_analysis.json"


class Analysis(KeptAnalysis):
    """An evoked analysis: its protocol, labels and groups, and the results of every folder measured so far."""

    FILE_NAME = FILE_NAME
    FORMAT = "EMA evoked analysis"
    METHOD = "protocol"
    RESULTS_VERSION = 1

    def protocol(self):
        return Protocol.from_dict(self.method) if self.method else None

    def same_method(self, protocol):
        """Whether the per-slice file is written does not change what is measured."""
        return _measuring(self.method) == _measuring(protocol.to_dict())


def _measuring(data):
    """A protocol's file contents without the switch for the per-slice file."""
    summary = {key: value for key, value in data.get("slice_summary", {}).items() if key != "file"}
    return {**data, "slice_summary": summary}


# ---------------------------------------------------------------------------
# What a run will do
# ---------------------------------------------------------------------------


def plan(analysis, protocol, selections):
    """What running this protocol on the folders of these selections would do."""
    replace_all = bool(analysis.folders) and not analysis.is_current(protocol)
    kept = {} if replace_all else analysis.folders
    to_measure, unchanged, missing, seen = [], [], [], set()
    for name in sorted(selections.folders):
        if not analysis.matches(name):
            continue
        folder = selections.recordings_folder / name
        key = folder.as_posix()
        seen.add(key)
        if not folder.is_dir():
            missing.append(folder)
            continue
        selection = selections.folders[name]
        stamp = folder_fingerprint(folder, selection)
        if key in kept and kept[key].fingerprint == stamp:
            unchanged.append(key)
        else:
            to_measure.append((folder, selection, stamp))
    others = [key for key in analysis.folders if key not in seen]
    return Plan(replace_all, to_measure, unchanged, others, missing)


def folder_fingerprint(folder, selection):
    """Changes when a folder's ROI, electrode, flags or recordings change (whether it was reviewed changes no number)."""
    return fingerprint(folder, roi=[selection.roi_center, selection.roi_radius_px, selection.image_shape],
                       electrode=selection.to_dict()["electrode"]["rows"], flagged=selection.flagged_files)


def choices(protocol, paths):
    """(path, listed recording) of each recording the protocol measures; path None if it is not in the folder."""
    if protocol.selection == EVERY:
        return [(path, None) for path in protocol.measured_files(paths)]
    names = {path.name.lower(): path for path in paths}
    return [(names.get(recording.file.lower()), recording) for recording in protocol.recordings]


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


class Cancelled(Exception):
    pass


def run(analysis, protocol, selections, the_plan=None, progress=None, cancelled=None, keep_others=True):
    """Measure what the plan says and keep the results in `analysis` (save it afterwards).

    With `keep_others` False, the results of folders that are not in these
    selections are dropped. `progress(done, total, text)` is called before
    each recording; when `cancelled()` returns True the run stops, keeping the
    folders measured so far. Returns the plan that was run.
    """
    the_plan = the_plan or plan(analysis, protocol, selections)
    if the_plan.replace_all:
        analysis.folders = {}
    if not keep_others:
        for key in the_plan.kept_others:
            analysis.folders.pop(key, None)
    analysis.measuring_with(protocol)
    analysis.recordings_folder = selections.recordings_folder.as_posix()
    for key in the_plan.unchanged:
        analysis.folders[key].reviewed = selections.of(Path(key)).reviewed
    total = sum(len(choices(protocol, list_recordings(folder))) for folder, _, _ in the_plan.to_measure)
    done = 0
    for folder, selection, stamp in the_plan.to_measure:
        def step(text):
            nonlocal done
            if cancelled is not None and cancelled():
                raise Cancelled()
            if progress is not None:
                progress(done, total, f"{selections.name_of(folder)}: {text}")
            done += 1

        try:
            result = measure_folder(protocol, folder, selection, step)
        except Cancelled:
            break
        result.name, result.recordings_folder = selections.name_of(folder), selections.recordings_folder.as_posix()
        result.fingerprint = stamp
        analysis.folders[folder.as_posix()] = result
    if progress is not None:
        progress(total, total, "Done")
    return the_plan


def measure_folder(protocol, folder, selection, step=None):
    """Measure every recording of one folder that the protocol measures, and summarise them."""
    result = FolderResult(folder.name, folder.parent.as_posix(), reviewed=selection.reviewed, measured=now())
    paths = list_recordings(folder)
    for path in paths:
        if selection.is_flagged(path.name):
            reason = selection.flagged_files[path.name]
            result.skipped.append([path.name, "Flagged in ROI Selection" + (f": {reason}" if reason else ".")])
    usable = [path for path in paths if not selection.is_flagged(path.name)]
    mask = selection.roi_mask()
    stack = lru_cache(maxsize=3)(load_stack)
    times = {}

    for path, recording in choices(protocol, usable):
        if step is not None:
            step(path.name if path is not None else recording.file)
        if path is None:
            name = recording.file
            flagged = any(p.name.lower() == name.lower() for p in paths)
            result.skipped.append([name, "Flagged in ROI Selection." if flagged else "Not in this folder."])
            continue
        partner, reason = find_partner(protocol, path, usable, recording, times)
        if protocol.uses_partner and partner is None:
            named = recording.unstimulated.strip() if recording else ""
            if named and any(p.name.lower() == named.lower() for p in paths):
                reason = f"Its unstimulated partner {named} is flagged in ROI Selection."
            result.skipped.append([path.name, reason])
            continue
        try:
            movie = stack(path)
            if movie.shape[1:] != tuple(selection.image_shape):
                raise ValueError(f"Its images are {movie.shape[2]} × {movie.shape[1]} pixels, not the size of the ROI file's.")
            other = stack(partner) if partner is not None else None
            trace = make_trace(protocol, movie[:, mask].mean(axis=1), None if other is None else other[:, mask].mean(axis=1), recording)
            measurement = measure(protocol, trace, recording)
            values = dict(measurement.values)
            if protocol.spatial_measures or protocol.near_to_far:
                pixels = make_movie(protocol, movie, other, recording)
                values.update(measure_spatial(protocol, pixels, selection.roi_center, selection.electrode_mask,
                                              measurement, recording).values)
        except Exception as error:  # noqa: BLE001  one recording that cannot be measured must not stop the run
            result.skipped.append([path.name, why_not_measured(error)])
            continue
        result.recordings.append(RecordingResult(
            path.name, values,
            partner=partner.name if partner is not None else "",
            condition=protocol.condition_of(path.name, recording),
            problems=list(measurement.problems) + _partner_notes(path, partner, times),
        ))
    if result.recordings:
        result.summary = summarise(protocol, [(r.condition, r.values) for r in result.recordings])
    return result


def _partner_notes(path, partner, times):
    """A note when the partner found by time stamp was made before the recording: none was made after it."""
    made, partner_made = times.get(path), times.get(partner)
    if partner is None or made is None or partner_made is None or partner_made >= made:
        return []
    minutes = (made - partner_made).total_seconds() / 60
    return [f"No unstimulated recording was made after it, so it is paired with {partner.name}, made "
            f"{minutes:.0f} min before it."]
