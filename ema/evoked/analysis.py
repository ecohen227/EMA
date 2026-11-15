"""The evoked analysis: measure the recordings of every folder in an ROI file with a protocol.

Everything about an analysis is kept in one file in its output folder,
`evoked_analysis.json`: the protocol, the labels and how the tables are
grouped, and the results, folder by folder. A new run measures only what is
new: folders that were not measured before, and folders whose ROI, electrode,
flags or recordings changed. Every other folder keeps its results, including
folders of an earlier ROI file. With another protocol, or another version of
EMA, everything is measured again. The two Excel files are then written from
the kept results (see ema.evoked.workbook).

Nothing here needs the GUI::

    from ema.evoked.analysis import Analysis, run
    from ema.evoked.protocol import Protocol
    from ema.roi_selection import Selections

    analysis = Analysis.open("my output folder")
    run(analysis, Protocol.load("my protocol.json"), Selections.load("roi_selections.json"))
    analysis.save()
"""

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .. import __version__
from ..labels import LabelSet, default_labels
from ..recordings import list_recordings, load_stack
from ..roi_selection.selections import folder_matches
from .measures import measure, summarise
from .protocol import EVERY, Protocol
from .spatial import measure_spatial
from .traces import find_partner, make_movie, make_trace

FILE_NAME = "evoked_analysis.json"
FORMAT = "EMA evoked analysis"
FORMAT_VERSION = 1


@dataclass
class RecordingResult:
    """The values measured on one recording."""

    file: str
    partner: str = ""  # its unstimulated partner, if the protocol uses one
    condition: float = None
    values: dict = field(default_factory=dict)  # measure name -> number (NaN when it could not be measured)
    problems: list = field(default_factory=list)  # what could not be measured, as sentences


@dataclass
class FolderResult:
    """The results of one recording folder (one slice)."""

    name: str  # its path inside the recordings folder
    recordings_folder: str
    fingerprint: str  # changes when its ROI, electrode, flags or recordings change
    reviewed: bool = False  # its ROI was reviewed in ROI Selection
    measured: str = ""  # when it was measured
    recordings: list = field(default_factory=list)  # RecordingResult
    skipped: list = field(default_factory=list)  # [file, why] of recordings that were not measured
    summary: dict = field(default_factory=dict)  # slice measure -> number

    @property
    def path(self):
        return Path(self.recordings_folder) / self.name


@dataclass
class Analysis:
    """An analysis: its settings and the results of every folder measured so far."""

    folder: Path = None  # the output folder
    protocol: dict = None  # the protocol the results were measured with, as saved in a protocol file
    ema_version: str = ""
    roi_file: str = ""
    labels: LabelSet = field(default_factory=default_labels)
    only_folders_with: list = field(default_factory=list)
    skip_folders_with: list = field(default_factory=list)
    group_by: list = field(default_factory=lambda: ["Genotype", "Treatment"])  # labels whose values make the groups
    slice_rows_by: str = ""  # a label whose values are the rows of the per-slice Prism sheets ('' for none)
    folders: dict = field(default_factory=dict)  # absolute path (posix) -> FolderResult

    @classmethod
    def open(cls, folder):
        """The analysis kept in an output folder, or a new one if there is none yet."""
        path = Path(folder) / FILE_NAME
        if not path.is_file():
            return cls(Path(folder))
        return cls.load(path)

    def protocol_object(self):
        return Protocol.from_dict(self.protocol) if self.protocol else None

    def is_current(self, protocol):
        """True if the kept results were measured with this protocol and this version of EMA."""
        return self.protocol == protocol.to_dict() and self.ema_version == __version__

    def matches(self, folder_name):
        return folder_matches(folder_name, self.only_folders_with, self.skip_folders_with)

    def folder_labels(self, result):
        return self.labels.read(self.labels.parts(result.name, result.recordings_folder))

    def save(self):
        content = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "ema_version": self.ema_version,
            "saved": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "protocol": self.protocol,
            "roi_file": self.roi_file,
            "folder_filter": {"only_with": self.only_folders_with, "skip_with": self.skip_folders_with},
            "labels": self.labels.to_dict(),
            "tables": {"group_by": self.group_by, "slice_rows_by": self.slice_rows_by},
            "folders": {path: _folder_to_dict(result) for path, result in sorted(self.folders.items())},
        }
        self.folder.mkdir(parents=True, exist_ok=True)
        temporary = self.folder / (FILE_NAME + ".tmp")
        temporary.write_text(json.dumps(content, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.folder / FILE_NAME)

    @classmethod
    def load(cls, path):
        path = Path(path)
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("format") != FORMAT:
            raise ValueError(f"{path.name} is not an EMA evoked analysis file.")
        if saved["format_version"] > FORMAT_VERSION:
            raise ValueError(f"{path.name} was written by a newer version of EMA ({saved['ema_version']}).")
        tables = saved.get("tables", {})
        return cls(
            folder=path.parent,
            protocol=saved["protocol"],
            ema_version=saved["ema_version"],
            roi_file=saved.get("roi_file", ""),
            labels=LabelSet.from_dict(saved["labels"]),
            only_folders_with=saved["folder_filter"]["only_with"],
            skip_folders_with=saved["folder_filter"]["skip_with"],
            group_by=tables.get("group_by", []),
            slice_rows_by=tables.get("slice_rows_by", ""),
            folders={key: _folder_from_dict(value) for key, value in saved["folders"].items()},
        )


# ---------------------------------------------------------------------------
# What a run will do
# ---------------------------------------------------------------------------


@dataclass
class Plan:
    """What a run will do, worked out before anything is read."""

    replace_all: bool  # the kept results were measured with another protocol or version, and are dropped
    to_measure: list  # (folder, FolderSelection, fingerprint) of the folders to measure
    unchanged: list  # absolute paths of folders whose kept results are used as they are
    kept_others: list  # absolute paths of kept folders that are not in this ROI file (or filter)
    missing: list  # folders of the ROI file that are not on this computer


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
        fingerprint = folder_fingerprint(folder, selection)
        if key in kept and kept[key].fingerprint == fingerprint:
            unchanged.append(key)
            continue
        to_measure.append((folder, selection, fingerprint))
    others = [key for key in analysis.folders if key not in seen]
    return Plan(replace_all, to_measure, unchanged, others, missing)


def folder_fingerprint(folder, selection):
    """A short text that changes when anything the results of a folder depend on changes.

    That is its ROI, electrode and flags, and the names, sizes and dates of its
    recordings. Whether its ROI was reviewed does not change any number.
    """
    content = {
        "roi": [selection.roi_center, selection.roi_radius_px, selection.image_shape],
        "electrode": selection.to_dict()["electrode"]["rows"],
        "flagged": selection.flagged_files,
        "files": [[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in list_recordings(folder)],
    }
    plain = json.dumps(content, default=lambda item: item.tolist() if hasattr(item, "tolist") else list(item))
    return hashlib.sha1(plain.encode()).hexdigest()[:16]


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
    selections are dropped. `progress(done, total, text)` is
    called before each recording; when `cancelled()` returns True the run
    stops, keeping the folders measured so far. Returns the plan that was run.
    """
    the_plan = the_plan or plan(analysis, protocol, selections)
    if the_plan.replace_all:
        analysis.folders = {}
    if not keep_others:
        for key in the_plan.kept_others:
            analysis.folders.pop(key, None)
    analysis.protocol, analysis.ema_version = protocol.to_dict(), __version__
    for key in the_plan.unchanged:
        analysis.folders[key].reviewed = selections.of(Path(key)).reviewed
    total = sum(len(choices(protocol, list_recordings(folder))) for folder, _, _ in the_plan.to_measure)
    done = 0
    for folder, selection, fingerprint in the_plan.to_measure:
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
        result.fingerprint = fingerprint
        analysis.folders[folder.as_posix()] = result
    if progress is not None:
        progress(total, total, "Done")
    return the_plan


def measure_folder(protocol, folder, selection, step=None):
    """Measure every recording of one folder that the protocol measures, and summarise them."""
    result = FolderResult(folder.name, "", "", selection.reviewed, datetime.now().isoformat(sep=" ", timespec="seconds"))
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
        except (OSError, ValueError, MemoryError) as error:
            result.skipped.append([path.name, str(error)])
            continue
        result.recordings.append(RecordingResult(
            path.name,
            partner.name if partner is not None else "",
            protocol.condition_of(path.name, recording),
            values,
            list(measurement.problems) + _partner_notes(path, partner, times),
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


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------


def _number(value):
    return None if value is None or (isinstance(value, float) and not math.isfinite(value)) else float(value)


def _folder_to_dict(result):
    return {
        "name": result.name,
        "recordings_folder": result.recordings_folder,
        "fingerprint": result.fingerprint,
        "reviewed": result.reviewed,
        "measured": result.measured,
        "recordings": [
            {"file": r.file, "partner": r.partner, "condition": r.condition,
             "values": {name: _number(value) for name, value in r.values.items()}, "problems": r.problems}
            for r in result.recordings
        ],
        "skipped": result.skipped,
        "summary": {name: _number(value) for name, value in result.summary.items()},
    }


def _folder_from_dict(data):
    nan = float("nan")
    return FolderResult(
        data["name"],
        data["recordings_folder"],
        data["fingerprint"],
        data["reviewed"],
        data["measured"],
        [
            RecordingResult(r["file"], r["partner"], r["condition"],
                            {name: nan if value is None else value for name, value in r["values"].items()}, r["problems"])
            for r in data["recordings"]
        ],
        [list(item) for item in data["skipped"]],
        {name: nan if value is None else value for name, value in data["summary"].items()},
    )
