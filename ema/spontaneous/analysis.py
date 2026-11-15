"""The spontaneous-event analysis: search the unstimulated recordings of every folder under a recordings folder.

It searches every folder that holds unstimulated recordings (see
Recordings); an ROI file is optional. It works like the evoked analysis (see
ema.evoked.analysis). Everything is kept in one file in the output folder, `spontaneous_analysis.json`: the
detector, the labels, the groups, and the results of every folder (each
recording's measures and every event's). A new run searches only folders
that are new or changed. Another detector, that is other settings or skip
words, searches everything again. Changing only which measures are reported
needs no new search: every measure is kept, and the tables show the chosen
ones.

Recordings are searched in parallel, each in a process of its own, since one
takes several seconds. Nothing here needs the GUI::

    from ema.spontaneous.analysis import Analysis, Recordings, run
    from ema.spontaneous.detector import Detector
    from ema.spontaneous.workbook import write_workbooks

    analysis = Analysis.open("my output folder")
    run(analysis, Detector.load("my detector.json"), Recordings("my recordings folder"))
    analysis.save()
    write_workbooks(analysis)
"""

import hashlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .. import __version__
from ..evoked.analysis import Plan
from ..labels import LabelSet, default_labels
from ..recordings import find_recording_folders, is_no_stim, list_recordings, load_stack
from ..roi_selection import RoiSettings, detect_folder
from ..roi_selection.selections import folder_matches
from .detection import detect
from .detector import Detector
from .measures import measure_events, measure_recording, summarise_slice

__all__ = ["Analysis", "FolderResult", "RecordingResult", "Recordings", "Plan", "plan", "run", "search_recording",
           "automatic_roi", "default_workers", "detection_part", "FILE_NAME"]

FILE_NAME = "spontaneous_analysis.json"
FORMAT = "EMA spontaneous analysis"
FORMAT_VERSION = 1


def default_workers():
    """Searches run at the same time: one per processor core but one, at most 8 (each needs up to about 1 GB)."""
    return max(1, min((os.cpu_count() or 2) - 1, 8))


@dataclass
class RecordingResult:
    """One searched recording: its per-recording measures and every event's measures."""

    file: str
    values: dict = field(default_factory=dict)
    events: list = field(default_factory=list)  # one dict per event, by onset


@dataclass
class FolderResult:
    """The results of one recording folder (one slice)."""

    name: str  # its path inside the recordings folder
    recordings_folder: str
    fingerprint: str = ""  # changes when its ROI, electrode, flags or recordings change
    reviewed: bool = False
    measured: str = ""
    recordings: list = field(default_factory=list)  # RecordingResult, by file name
    skipped: list = field(default_factory=list)  # [file, why] of recordings that were not searched
    summary: dict = field(default_factory=dict)  # the per-slice measures (without the summaries of event measures)
    source: str = ""  # where its electrode and release centre came from: ROI file (reviewed or not), automatic, none
    notes: list = field(default_factory=list)  # what to tell the user about the folder

    @property
    def path(self):
        return Path(self.recordings_folder) / self.name

    def events(self):
        """(recording index, event) of every event of the slice."""
        return [(i, event) for i, recording in enumerate(self.recordings) for event in recording.events]


def detection_part(detector):
    """What decides which events are found and how they are measured: the settings and the skip words."""
    data = detector.to_dict()
    return {"settings": data["settings"], "recordings": data["recordings"]}


@dataclass
class Analysis:
    """A spontaneous-event analysis: its settings and the results of every folder searched so far."""

    folder: Path = None
    detector: dict = None  # the detector the results were searched with, as saved in a detector file
    ema_version: str = ""
    roi_file: str = ""
    recordings_folder: str = ""
    labels: LabelSet = field(default_factory=default_labels)
    only_folders_with: list = field(default_factory=list)
    skip_folders_with: list = field(default_factory=list)
    group_by: list = field(default_factory=lambda: ["Genotype", "Treatment"])
    slice_rows_by: str = ""
    folders: dict = field(default_factory=dict)  # absolute path (posix) -> FolderResult

    @property
    def method(self):
        return self.detector

    @classmethod
    def open(cls, folder):
        path = Path(folder) / FILE_NAME
        return cls.load(path) if path.is_file() else cls(Path(folder))

    def detector_object(self):
        return Detector.from_dict(self.detector) if self.detector else None

    def is_current(self, detector):
        """True if the kept results were searched with these settings and skip words, and this version of EMA."""
        return (self.detector is not None and self.ema_version == __version__
                and detection_part(Detector.from_dict(self.detector)) == detection_part(detector))

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
            "detector": self.detector,
            "roi_file": self.roi_file,
            "recordings_folder": self.recordings_folder,
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
            raise ValueError(f"{path.name} is not an EMA spontaneous analysis file.")
        if saved["format_version"] > FORMAT_VERSION:
            raise ValueError(f"{path.name} was written by a newer version of EMA ({saved['ema_version']}).")
        tables = saved.get("tables", {})
        return cls(
            folder=path.parent,
            detector=saved["detector"],
            ema_version=saved["ema_version"],
            roi_file=saved.get("roi_file", ""),
            recordings_folder=saved.get("recordings_folder", ""),
            labels=LabelSet.from_dict(saved["labels"]),
            only_folders_with=saved["folder_filter"]["only_with"],
            skip_folders_with=saved["folder_filter"]["skip_with"],
            group_by=tables.get("group_by", []),
            slice_rows_by=tables.get("slice_rows_by", ""),
            folders={key: _folder_from_dict(value) for key, value in saved["folders"].items()},
        )


# ---------------------------------------------------------------------------
# What is searched
# ---------------------------------------------------------------------------

FROM_ROI_FILE, REVIEWED, AUTOMATIC, NONE = "ROI file", "ROI file, reviewed", "automatic", "none"


@dataclass
class Recordings:
    """What an analysis searches: every folder under a recordings folder that holds unstimulated recordings.

    With `selections` (an ROI file made for the same recordings folder), a
    folder it covers uses its reviewed electrode, release centre and flags;
    every other folder's are found automatically from its stimulated
    recordings, as in ROI Selection.
    """

    root: Path
    selections: object = None  # Selections, or None
    _found: list = None

    def __post_init__(self):
        self.root = Path(self.root)
        if self.selections is not None and Path(self.selections.recordings_folder).resolve() != self.root.resolve():
            self.selections = None  # made for another recordings folder: not used

    def folders(self):
        """The folders with at least one unstimulated recording, by path (looked up once)."""
        if self._found is None:
            self._found = [f for f in find_recording_folders(self.root) if any(is_no_stim(p) for p in list_recordings(f))]
        return self._found

    def name_of(self, folder):
        return Path(folder).relative_to(self.root).as_posix()

    def selection(self, folder):
        """The ROI file's selection of a folder, or None."""
        return self.selections.of(folder) if self.selections is not None else None


def folder_fingerprint(folder, selection):
    """A short text that changes when anything a folder's results depend on changes: its ROI file entry (or none),
    and the names, sizes and dates of its recordings."""
    content = {"files": [[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in list_recordings(folder)]}
    if selection is not None:
        content.update(roi=[selection.roi_center, selection.image_shape], electrode=selection.to_dict()["electrode"]["rows"],
                       flagged=selection.flagged_files)
    plain = json.dumps(content, default=lambda item: item.tolist() if hasattr(item, "tolist") else list(item))
    return hashlib.sha1(plain.encode()).hexdigest()[:16]


def plan(analysis, detector, recordings):
    """What searching these recordings with this detector would do (see ema.evoked.analysis.Plan)."""
    replace_all = bool(analysis.folders) and not analysis.is_current(detector)
    kept = {} if replace_all else analysis.folders
    to_measure, unchanged, seen = [], [], set()
    for folder in recordings.folders():
        if not analysis.matches(recordings.name_of(folder)):
            continue
        key = folder.as_posix()
        seen.add(key)
        selection = recordings.selection(folder)
        fingerprint = folder_fingerprint(folder, selection)
        if key in kept and kept[key].fingerprint == fingerprint:
            unchanged.append(key)
        else:
            to_measure.append((folder, selection, fingerprint))
    others = [key for key in analysis.folders if key not in seen]
    return Plan(replace_all, to_measure, unchanged, others, [])


def automatic_roi(folder):
    """(release centre, electrode mask, source) of a folder found from its stimulated recordings, as in ROI Selection;
    (None, None, NONE) when it has none."""
    try:
        found = detect_folder(folder, RoiSettings())
    except (OSError, ValueError):
        return None, None, NONE
    return tuple(found.center), found.electrode, AUTOMATIC


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def search_recording(path, electrode, settings, center, image_shape=None):
    """Search one recording: (per-recording measures, events by onset, tissue mask). Runs in a worker process.

    With `center` None, the folder's release centre and electrode are found
    automatically (see automatic_roi) and the source is returned too.
    """
    source = None
    if center is None:
        center, electrode, source = automatic_roi(Path(path).parent)
    stack = load_stack(path)
    if image_shape is not None and stack.shape[1:] != tuple(image_shape):
        raise ValueError(f"Its images are {stack.shape[2]} × {stack.shape[1]} pixels, not the size of the ROI file's.")
    detection = detect(stack, electrode, settings)
    events = sorted(measure_events(detection, settings, center, electrode), key=lambda e: e["onset"])
    return measure_recording(detection, settings), events, detection.tissue, source


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
    analysis.detector, analysis.ema_version = detector.to_dict(), __version__
    analysis.recordings_folder = recordings.root.as_posix()

    folders, tasks = {}, []
    for folder, selection, fingerprint in the_plan.to_measure:
        result = FolderResult(recordings.name_of(folder), recordings.root.as_posix(), fingerprint,
                              selection is not None and selection.reviewed, datetime.now().isoformat(sep=" ", timespec="seconds"))
        if selection is not None:
            result.source = REVIEWED if selection.reviewed else FROM_ROI_FILE
            roi = (selection.electrode_mask, detector.settings, tuple(selection.roi_center), tuple(selection.image_shape))
        else:
            roi = (None, detector.settings, None, None)
        for path in detector.searched_files(list_recordings(folder)):
            if selection is not None and selection.is_flagged(path.name):
                reason = selection.flagged_files[path.name]
                result.skipped.append([path.name, "Flagged in ROI Selection" + (f": {reason}" if reason else ".")])
            else:
                tasks.append((folder.as_posix(), path, *roi))
        folders[folder.as_posix()] = (result, {})
    pending = {key: sum(task[0] == key for task in tasks) for key in folders}
    for key, count in pending.items():
        if count == 0:
            _finish(analysis, key, *folders[key], detector)

    total, done = len(tasks), 0

    def report(key, path, outcome):
        nonlocal done
        done += 1
        result, found = folders[key]
        found[path.name] = outcome
        pending[key] -= 1
        if pending[key] == 0:
            _finish(analysis, key, result, found, detector)
        if progress is not None:
            progress(done, total, f"{result.name}: {path.name}")

    workers = workers or default_workers()
    if workers == 1 or total <= 1:
        for task in tasks:
            if cancelled is not None and cancelled():
                break
            report(task[0], task[1], _attempt(task))
    else:
        _searched_in_processes(tasks, workers, report, cancelled)
    if progress is not None:
        progress(total, total, "Done")
    return the_plan


THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")


def _searched_in_processes(tasks, workers, report, cancelled):
    """Search the tasks in worker processes, each limited to one thread so that the workers share the cores."""
    before = {name: os.environ.get(name) for name in THREADS}
    os.environ.update(dict.fromkeys(THREADS, "1"))  # read by numpy as each worker starts
    try:
        with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
            futures = {pool.submit(search_recording, *task[1:]): task for task in tasks}
            for future in as_completed(futures):
                if cancelled is not None and cancelled():
                    pool.shutdown(wait=True, cancel_futures=True)
                    break
                task = futures[future]
                try:
                    outcome = future.result()
                except (OSError, ValueError, MemoryError) as error:
                    outcome = error
                report(task[0], task[1], outcome)
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _attempt(task):
    try:
        return search_recording(*task[1:])
    except (OSError, ValueError, MemoryError) as error:
        return error


SOURCE_NOTES = {
    AUTOMATIC: "No ROI file entry: the electrode and the release centre were found automatically from the folder's "
               "stimulated recordings.",
    NONE: "No ROI file entry and no stimulated recording: searched without an electrode, and the place measures are empty.",
}


def _finish(analysis, key, result, found, detector):
    """Keep a folder whose recordings have all been searched, with its per-slice measures."""
    tissue = None
    for name in sorted(found, key=str.lower):
        outcome = found[name]
        if isinstance(outcome, Exception):
            result.skipped.append([name, str(outcome)])
            continue
        values, events, recording_tissue, source = outcome
        tissue = recording_tissue if tissue is None else tissue
        if source is not None:
            result.source = source
        result.recordings.append(RecordingResult(name, values, events))
    if result.source in SOURCE_NOTES:
        result.notes.append(SOURCE_NOTES[result.source])
    if result.recordings:
        result.summary = summarise_slice([r.values for r in result.recordings], result.events(), detector.settings, tissue,
                                         None, [], [], seed=0)
    analysis.folders[key] = result


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------


def _number(value):
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _numbers(values):
    return {name: _number(value) for name, value in values.items()}


def _back(values):
    return {name: float("nan") if value is None else value for name, value in values.items()}


def _folder_to_dict(result):
    return {
        "name": result.name,
        "recordings_folder": result.recordings_folder,
        "fingerprint": result.fingerprint,
        "reviewed": result.reviewed,
        "measured": result.measured,
        "recordings": [{"file": r.file, "values": _numbers(r.values), "events": [_numbers(e) for e in r.events]}
                       for r in result.recordings],
        "skipped": result.skipped,
        "summary": _numbers(result.summary),
        "electrode_and_centre": result.source,
        "notes": result.notes,
    }


def _folder_from_dict(data):
    return FolderResult(
        data["name"], data["recordings_folder"], data["fingerprint"], data["reviewed"], data["measured"],
        [RecordingResult(r["file"], _back(r["values"]), [_back(e) for e in r["events"]]) for r in data["recordings"]],
        [list(item) for item in data["skipped"]],
        _back(data["summary"]),
        data.get("electrode_and_centre", ""),
        list(data.get("notes", [])),
    )
