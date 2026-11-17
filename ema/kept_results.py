"""What an analysis keeps in its output folder, and what a new run measures again.

Both analyses (ema.evoked.analysis and ema.spontaneous.analysis) keep
everything in one JSON file in their output folder: the protocol or detector
the results were measured with (as saved in its file), the labels, how the
tables are grouped, and the results, folder by folder. A new run measures only
the folders that are new or changed (see `fingerprint`). Everything is measured
again with another protocol or detector, or when this EMA computes results
differently from the one that measured them (see KeptAnalysis.RESULTS_VERSION).
"""

import hashlib
import json
import math
import os
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from . import __version__
from .labels import LabelSet, default_labels
from .recordings import folder_matches, list_recordings


@dataclass
class Plan:
    """What a run will do, worked out before any recording is read."""

    replace_all: bool  # the kept results were measured with another protocol or detector, and are dropped
    to_measure: list  # (folder, its ROI file entry or None, fingerprint) of the folders to measure
    unchanged: list  # absolute paths of folders whose kept results are used as they are
    kept_others: list  # absolute paths of kept folders that are not measured now (not in the ROI file or filter)
    missing: list  # folders of the ROI file that are not on this computer


@dataclass
class RecordingResult:
    """What was measured on one recording."""

    file: str
    values: dict = field(default_factory=dict)  # measure name -> number (NaN when it could not be measured)
    partner: str = ""  # evoked: its unstimulated partner, if the protocol uses one
    condition: float = None  # evoked: its condition, such as the current
    problems: list = field(default_factory=list)  # evoked: what could not be measured, as sentences
    events: list = field(default_factory=list)  # spontaneous: one dict of measures per event, by onset


@dataclass
class FolderResult:
    """The results of one recording folder (one slice)."""

    name: str  # its path inside the recordings folder
    recordings_folder: str
    fingerprint: str = ""  # see `fingerprint`
    reviewed: bool = False  # its ROI was reviewed in ROI Selection
    measured: str = ""  # when it was measured
    recordings: list = field(default_factory=list)  # RecordingResult
    skipped: list = field(default_factory=list)  # [file, why] of recordings that were not measured
    summary: dict = field(default_factory=dict)  # per-slice measure -> number
    source: str = ""  # spontaneous: where its electrode and ROI centre came from
    notes: list = field(default_factory=list)  # what to tell the user about the folder

    @property
    def path(self):
        return Path(self.recordings_folder) / self.name

    def events(self):
        """(recording index, event) of every event of the slice (spontaneous)."""
        return [(i, event) for i, recording in enumerate(self.recordings) for event in recording.events]


def now():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


@dataclass
class KeptAnalysis:
    """An analysis: its settings and the results of every folder measured so far.

    Each analysis says what its file is called and what it measures with.
    RESULTS_VERSION is raised by one whenever a change to EMA changes any
    number an analysis writes, so that results kept by an earlier EMA are
    measured again.
    """

    FILE_NAME: ClassVar[str] = ""
    FORMAT: ClassVar[str] = ""
    FORMAT_VERSION: ClassVar[int] = 1
    METHOD: ClassVar[str] = ""  # "protocol" or "detector": what the results are measured with
    RESULTS_VERSION: ClassVar[int] = 1

    folder: Path = None  # the output folder
    method: dict = None  # the protocol or detector the results were measured with, as saved in its file
    results_version: int = 0
    ema_version: str = ""  # the EMA that measured them
    roi_file: str = ""
    recordings_folder: str = ""
    labels: LabelSet = field(default_factory=default_labels)
    only_folders_with: list = field(default_factory=list)
    skip_folders_with: list = field(default_factory=list)
    group_by: list = field(default_factory=lambda: ["Genotype", "Treatment"])  # labels whose values make the groups
    slice_rows_by: str = ""  # a label whose values are the rows of the per-slice Prism sheets ('' for none)
    folders: dict = field(default_factory=dict)  # absolute path (posix) -> FolderResult

    @classmethod
    def open(cls, folder):
        """The analysis kept in an output folder, or a new one if there is none yet."""
        path = Path(folder) / cls.FILE_NAME
        return cls.load(path) if path.is_file() else cls(Path(folder))

    def is_current(self, method):
        """True if the kept results were measured with this protocol or detector and compute as this EMA does."""
        return self.method is not None and self.results_version == self.RESULTS_VERSION and self.same_method(method)

    def same_method(self, method):
        return self.method == method.to_dict()

    def matches(self, folder_name):
        return folder_matches(folder_name, self.only_folders_with, self.skip_folders_with)

    def folder_labels(self, result):
        return self.labels.read(self.labels.parts(result.name, result.recordings_folder))

    def measuring_with(self, method):
        """Note what the results from now on are measured with."""
        self.method, self.results_version, self.ema_version = method.to_dict(), self.RESULTS_VERSION, __version__

    def save(self):
        content = {
            "format": self.FORMAT,
            "format_version": self.FORMAT_VERSION,
            "results_version": self.results_version,
            "ema_version": self.ema_version,
            "saved": now(),
            self.METHOD: self.method,
            "roi_file": self.roi_file,
            "recordings_folder": self.recordings_folder,
            "folder_filter": {"only_with": self.only_folders_with, "skip_with": self.skip_folders_with},
            "labels": self.labels.to_dict(),
            "tables": {"group_by": self.group_by, "slice_rows_by": self.slice_rows_by},
            "folders": {path: _folder_to_dict(result) for path, result in sorted(self.folders.items())},
        }
        write_json(self.folder / self.FILE_NAME, content)

    @classmethod
    def load(cls, path):
        """Read a file written by `save`. Raises OSError, or ValueError when it is not such a file or is damaged."""
        path = Path(path)
        saved = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(saved, dict) or saved.get("format") != cls.FORMAT:
            raise ValueError(f"{path.name} is not an {cls.FORMAT} file.")
        if saved.get("format_version", 1) > cls.FORMAT_VERSION:
            raise ValueError(f"{path.name} was written by a newer version of EMA ({saved.get('ema_version')}).")
        try:
            tables, folder_filter = saved.get("tables", {}), saved.get("folder_filter", {})
            return cls(
                folder=path.parent,
                method=saved[cls.METHOD],
                results_version=int(saved.get("results_version", 0)),
                ema_version=str(saved.get("ema_version", "")),
                roi_file=saved.get("roi_file", ""),
                recordings_folder=saved.get("recordings_folder", ""),
                labels=LabelSet.from_dict(saved["labels"]),
                only_folders_with=list(folder_filter.get("only_with", [])),
                skip_folders_with=list(folder_filter.get("skip_with", [])),
                group_by=list(tables.get("group_by", [])),
                slice_rows_by=tables.get("slice_rows_by", ""),
                folders={key: _folder_from_dict(value) for key, value in saved["folders"].items()},
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError(f"{path.name} is incomplete or damaged ({error!r}).") from error


def fingerprint(folder, **parts):
    """A short text that changes when anything a folder's results depend on changes.

    That is `parts` (such as its ROI, electrode and flags) and the names, sizes
    and dates of its recordings. When the fingerprint of a kept folder is the
    same, its results are kept.
    """
    content = {**parts, "files": [[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in list_recordings(folder)]}
    plain = json.dumps(content, default=lambda item: item.tolist() if hasattr(item, "tolist") else list(item))
    return hashlib.sha1(plain.encode()).hexdigest()[:16]


def why_not_measured(error):
    """What to tell the user about an error that stopped one recording from being measured."""
    if isinstance(error, MemoryError):
        return "There was not enough memory to measure it."
    if isinstance(error, BrokenProcessPool):
        return "The process measuring it stopped unexpectedly (often for lack of memory). Run again to measure it."
    if isinstance(error, (OSError, ValueError)):
        return str(error)
    return f"Unexpected error (please report it): {type(error).__name__}: {error}"


def write_json(path, content):
    """Write a JSON file in full or not at all: a crash never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(content, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


# ---------------------------------------------------------------------------
# Results in the file: NaN is written as null
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


def _recording_to_dict(r):
    found = {"file": r.file, "values": _numbers(r.values)}
    if r.partner:
        found["partner"] = r.partner
    if r.condition is not None:
        found["condition"] = r.condition
    if r.problems:
        found["problems"] = r.problems
    if r.events:
        found["events"] = [_numbers(e) for e in r.events]
    return found


def _recording_from_dict(data):
    return RecordingResult(data["file"], _back(data["values"]), data.get("partner", ""), data.get("condition"),
                           list(data.get("problems", [])), [_back(e) for e in data.get("events", [])])


def _folder_to_dict(result):
    return {
        "name": result.name,
        "recordings_folder": result.recordings_folder,
        "fingerprint": result.fingerprint,
        "reviewed": result.reviewed,
        "measured": result.measured,
        "recordings": [_recording_to_dict(r) for r in result.recordings],
        "skipped": result.skipped,
        "summary": _numbers(result.summary),
        "electrode_and_centre": result.source,
        "notes": result.notes,
    }


def _folder_from_dict(data):
    return FolderResult(
        data["name"], data["recordings_folder"], data["fingerprint"], data["reviewed"], data["measured"],
        [_recording_from_dict(r) for r in data["recordings"]],
        [list(item) for item in data["skipped"]],
        _back(data["summary"]),
        data.get("electrode_and_centre", ""),
        list(data.get("notes", [])),
    )
