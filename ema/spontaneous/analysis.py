"""The spontaneous-event analysis: search the unstimulated recordings of every folder under a recordings folder.

It searches every folder that holds unstimulated recordings (see
Recordings); an ROI file is optional. It works like the evoked analysis:
everything is kept in one file in the output folder,
`spontaneous_analysis.json` (see ema.kept_results), and a new run searches only
the folders that are new or changed. A detector with other settings or skip
words searches everything again. Changing only which measures are reported
needs no new search: every measure is kept, and the tables show the chosen
ones.

Recordings are searched in parallel, each in a process of its own, since one
takes several seconds. Nothing here needs the GUI::

    from ema.spontaneous.analysis import Analysis, Recordings, run
    from ema.spontaneous.detector import Detector
    from ema.spontaneous.workbook import write_workbooks

    if __name__ == "__main__":  # needed on Windows, where each worker process starts this script again
        analysis = Analysis.open("my output folder")
        run(analysis, Detector.load("my detector.json"), Recordings("my recordings folder"))
        analysis.save()
        write_workbooks(analysis)
"""

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..kept_results import FolderResult, KeptAnalysis, Plan, RecordingResult, fingerprint, now, why_not_measured
from ..recordings import find_recording_folders, is_no_stim, list_recordings, load_stack
from ..roi_selection import RoiSettings, detect_folder
from .detection import detect
from .detector import Detector
from .measures import measure_events, measure_recording, summarise_slice

FILE_NAME = "spontaneous_analysis.json"
FROM_ROI_FILE, REVIEWED, AUTOMATIC, NONE = "ROI file", "ROI file, reviewed", "automatic", "none"


def default_workers():
    """Searches run at the same time: one per processor core but one, at most 8 (each needs up to about 1 GB)."""
    return max(1, min((os.cpu_count() or 2) - 1, 8))


def detection_part(detector):
    """What decides which events are found and how they are measured: the settings and the skip words."""
    data = detector.to_dict()
    return {"settings": data["settings"], "recordings": data["recordings"]}


class Analysis(KeptAnalysis):
    """A spontaneous-event analysis: its detector, labels and groups, and the results of every folder searched so far."""

    FILE_NAME = FILE_NAME
    FORMAT = "EMA spontaneous analysis"
    METHOD = "detector"
    RESULTS_VERSION = 1

    def detector(self):
        return Detector.from_dict(self.method) if self.method else None

    def same_method(self, detector):
        """Only the settings and skip words count: the chosen measures only change the tables."""
        return detection_part(Detector.from_dict(self.method)) == detection_part(detector)


# ---------------------------------------------------------------------------
# What is searched
# ---------------------------------------------------------------------------


@dataclass
class Recordings:
    """What an analysis searches: every folder under a recordings folder that holds unstimulated recordings.

    With `selections` (an ROI file made for the same recordings folder), a
    folder it covers uses its reviewed electrode, ROI centre and flags; every
    other folder's are found automatically from its stimulated recordings, as
    in ROI Selection.
    """

    root: Path
    selections: object = None  # Selections, or None

    def __post_init__(self):
        self.root = Path(self.root)
        self._found = None
        if self.selections is not None and Path(self.selections.recordings_folder).resolve() != self.root.resolve():
            self.selections = None  # made for another recordings folder: not used

    def folders(self):
        """The folders with at least one unstimulated recording, by path (looked up once)."""
        if self._found is None:
            self._found = [f for f in find_recording_folders(self.root) if any(is_no_stim(p) for p in list_recordings(f))]
        return self._found

    def with_selections(self, selections):
        """The same folders (without looking them up again), with another ROI file."""
        other = Recordings(self.root, selections)
        other._found = self._found
        return other

    def name_of(self, folder):
        return Path(folder).relative_to(self.root).as_posix()

    def selection(self, folder):
        """The ROI file's selection of a folder, or None."""
        return self.selections.of(folder) if self.selections is not None else None


def folder_fingerprint(folder, selection):
    """Changes when a folder's ROI file entry (or that it has none) or its recordings change."""
    if selection is None:
        return fingerprint(folder)
    return fingerprint(folder, roi=[selection.roi_center, selection.image_shape],
                       electrode=selection.to_dict()["electrode"]["rows"], flagged=selection.flagged_files)


def plan(analysis, detector, recordings):
    """What searching these recordings with this detector would do."""
    replace_all = bool(analysis.folders) and not analysis.is_current(detector)
    kept = {} if replace_all else analysis.folders
    to_measure, unchanged, seen = [], [], set()
    for folder in recordings.folders():
        if not analysis.matches(recordings.name_of(folder)):
            continue
        key = folder.as_posix()
        seen.add(key)
        selection = recordings.selection(folder)
        stamp = folder_fingerprint(folder, selection)
        if key in kept and kept[key].fingerprint == stamp:
            unchanged.append(key)
        else:
            to_measure.append((folder, selection, stamp))
    others = [key for key in analysis.folders if key not in seen]
    return Plan(replace_all, to_measure, unchanged, others, [])


def automatic_roi(folder):
    """(ROI centre, electrode mask, source) of a folder, found from its stimulated recordings as in ROI Selection;
    (None, None, NONE) when it has none."""
    try:
        found = detect_folder(folder, RoiSettings())
    except Exception:  # noqa: BLE001  no usable stimulated recording: searched without an electrode
        return None, None, NONE
    return tuple(found.center), found.electrode, AUTOMATIC


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def search_recording(path, electrode, settings, center, image_shape=None):
    """Search one recording: (per-recording measures, events by onset, tissue mask). Runs in a worker process."""
    stack = load_stack(path)
    if image_shape is not None and stack.shape[1:] != tuple(image_shape):
        raise ValueError(f"Its images are {stack.shape[2]} × {stack.shape[1]} pixels, not the size of the ROI file's.")
    detection = detect(stack, electrode, settings)
    events = sorted(measure_events(detection, settings, center, electrode), key=lambda e: e["onset"])
    return measure_recording(detection, settings), events, detection.tissue


def run(analysis, detector, recordings, the_plan=None, progress=None, cancelled=None, keep_others=True, workers=None):
    """Search what the plan says and keep the results in `analysis` (save it afterwards).

    `recordings` says what is searched (see Recordings). `workers` processes
    search at the same time (1: one after the other, in this process).
    `progress(done, total, text)` is called as recordings are done; when
    `cancelled()` returns True the run stops, keeping the folders finished so
    far. Returns the plan that was run.
    """
    the_plan = the_plan or plan(analysis, detector, recordings)
    if the_plan.replace_all:
        analysis.folders = {}
    if not keep_others:
        for key in the_plan.kept_others:
            analysis.folders.pop(key, None)
    analysis.measuring_with(detector)
    analysis.recordings_folder = recordings.root.as_posix()

    folders, searched = {}, {}
    for folder, selection, stamp in the_plan.to_measure:
        result = FolderResult(recordings.name_of(folder), recordings.root.as_posix(), stamp,
                              selection is not None and selection.reviewed, now())
        searched[folder] = []
        for path in detector.searched_files(list_recordings(folder)):
            if selection is not None and selection.is_flagged(path.name):
                reason = selection.flagged_files[path.name]
                result.skipped.append([path.name, "Flagged in ROI Selection" + (f": {reason}" if reason else ".")])
            else:
                searched[folder].append(path)
        folders[folder] = (result, {})
    total, done = sum(len(paths) for paths in searched.values()), 0

    def report(folder, path, outcome):
        nonlocal done
        done += 1
        result, found = folders[folder]
        found[path.name] = outcome
        if len(found) == len(searched[folder]):
            _finish(analysis, folder, result, found, detector)
        if progress is not None:
            progress(done, total, f"{result.name}: {path.name}")

    workers = min(workers or default_workers(), max(total, 1))
    with one_thread_each(workers) as pool:
        tasks = []
        automatic = [folder for folder, selection, _ in the_plan.to_measure if selection is None and searched[folder]]
        if automatic and progress is not None:
            progress(0, total, f"Finding the electrode and ROI centre of {len(automatic)} folders")
        rois = dict(zip(automatic, pool.map(automatic_roi, automatic) if pool else map(automatic_roi, automatic)))
        for folder, selection, _ in the_plan.to_measure:
            result = folders[folder][0]
            if selection is not None:
                result.source = REVIEWED if selection.reviewed else FROM_ROI_FILE
                roi = (selection.electrode_mask, tuple(selection.roi_center), tuple(selection.image_shape))
            elif folder in rois:
                center, electrode, result.source = rois[folder]
                roi = (electrode, center, None)
            if not searched[folder]:
                _finish(analysis, folder, result, {}, detector)
            for path in searched[folder]:
                electrode, center, shape = roi
                tasks.append((folder, path, (path, electrode, detector.settings, center, shape)))

        if pool is None:
            for folder, path, arguments in tasks:
                if cancelled is not None and cancelled():
                    break
                try:
                    outcome = search_recording(*arguments)
                except Exception as error:  # noqa: BLE001  one recording must not stop the run
                    outcome = error
                report(folder, path, outcome)
        else:
            futures = {pool.submit(search_recording, *arguments): (folder, path) for folder, path, arguments in tasks}
            for future in as_completed(futures):
                if cancelled is not None and cancelled():
                    pool.shutdown(wait=True, cancel_futures=True)
                    break
                try:
                    outcome = future.result()
                except Exception as error:  # noqa: BLE001  one recording, or a process that died, must not stop the run
                    outcome = error
                report(*futures[future], outcome)
    if progress is not None:
        progress(total, total, "Done")
    return the_plan


THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")


@contextmanager
def one_thread_each(workers):
    """A pool of `workers` processes, or None for one worker.

    Each process is limited to one thread, so that the processes share the
    processor cores instead of competing for them. The limit is set in this
    process's environment while the pool starts its processes, and taken off
    afterwards.
    """
    if workers <= 1:
        yield None
        return
    before = {name: os.environ.get(name) for name in THREADS}
    os.environ.update(dict.fromkeys(THREADS, "1"))
    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            yield pool
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


SOURCE_NOTES = {
    AUTOMATIC: "No ROI file entry: the electrode and the ROI centre were found automatically from the folder's "
               "stimulated recordings.",
    NONE: "No ROI file entry and no stimulated recording: searched without an electrode, and the place measures are empty.",
}


def _finish(analysis, folder, result, found, detector):
    """Keep a folder whose recordings have all been searched, with its per-slice measures."""
    tissue = None
    for name in sorted(found, key=str.lower):
        outcome = found[name]
        if isinstance(outcome, Exception):
            result.skipped.append([name, why_not_measured(outcome)])
            continue
        values, events, recording_tissue = outcome
        tissue = recording_tissue if tissue is None else tissue
        result.recordings.append(RecordingResult(name, values, events=events))
    if result.source in SOURCE_NOTES:
        result.notes.append(SOURCE_NOTES[result.source])
    if result.recordings:
        result.summary = summarise_slice([r.values for r in result.recordings], result.events(), detector.settings, tissue)
    analysis.folders[folder.as_posix()] = result
