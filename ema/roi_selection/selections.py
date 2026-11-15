"""The ROI file: what was selected in every recording folder.

One JSON file, `roi_selections.json`, holds the settings and, for every
recording folder, its ROI, electrode mask and flagged files. Other EMA
packages read it with `Selections.load`.
"""

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from .. import __version__
from .detection import roi_mask
from .settings import RoiSettings

FILE_NAME = "roi_selections.json"
FORMAT = "EMA ROI selections"
FORMAT_VERSION = 1
AUTOMATIC, MANUAL = "automatic", "manual"


@dataclass
class FolderSelection:
    """The ROI, electrode mask and flags of one recording folder."""

    image_shape: tuple  # (rows, columns)
    roi_center: tuple  # (x, y) in pixels
    roi_radius_px: float
    electrode_mask: np.ndarray  # True under the electrode
    roi_source: str = AUTOMATIC
    electrode_source: str = AUTOMATIC
    automatic_roi_center: tuple = None
    peak_response_percent: float = None  # dF/F at the automatic ROI
    detection_files: list = field(default_factory=list)
    flagged_files: dict = field(default_factory=dict)  # file name -> reason
    reviewed: bool = False

    @classmethod
    def from_detection(cls, detection, settings):
        return cls(
            image_shape=detection.response.shape,
            roi_center=detection.center,
            roi_radius_px=settings.roi_radius_px,
            electrode_mask=detection.electrode.copy(),
            automatic_roi_center=detection.center,
            peak_response_percent=round(detection.peak_response * 100, 2),
            detection_files=list(detection.files),
        )

    def roi_mask(self):
        """True for the pixels inside the ROI."""
        return roi_mask(self.image_shape, self.roi_center, self.roi_radius_px)

    def is_flagged(self, file_name):
        """True if the recording with this file name was flagged."""
        return file_name in self.flagged_files

    @property
    def is_manual(self):
        return MANUAL in (self.roi_source, self.electrode_source)

    def to_dict(self):
        return {
            "image_shape": list(self.image_shape),
            "roi": {
                "x": self.roi_center[0],
                "y": self.roi_center[1],
                "radius_px": self.roi_radius_px,
                "source": self.roi_source,
            },
            "automatic_roi": {
                "x": self.automatic_roi_center[0],
                "y": self.automatic_roi_center[1],
                "peak_response_percent": self.peak_response_percent,
                "files": self.detection_files,
            },
            "electrode": {
                "source": self.electrode_source,
                "pixels": int(self.electrode_mask.sum()),
                "rows": mask_to_text(self.electrode_mask),
            },
            "flagged_files": self.flagged_files,
            "reviewed": self.reviewed,
        }

    @classmethod
    def from_dict(cls, saved):
        shape = tuple(saved["image_shape"])
        roi, automatic, electrode = saved["roi"], saved["automatic_roi"], saved["electrode"]
        return cls(
            image_shape=shape,
            roi_center=(roi["x"], roi["y"]),
            roi_radius_px=roi["radius_px"],
            roi_source=roi["source"],
            electrode_mask=text_to_mask(electrode["rows"], shape),
            electrode_source=electrode["source"],
            automatic_roi_center=(automatic["x"], automatic["y"]),
            peak_response_percent=automatic["peak_response_percent"],
            detection_files=automatic["files"],
            flagged_files=saved["flagged_files"],
            reviewed=saved["reviewed"],
        )


class Selections:
    """Every folder's selection, with the settings they were made with."""

    def __init__(self, recordings_folder, settings=None):
        self.recordings_folder = Path(recordings_folder)
        self.settings = settings or RoiSettings()
        self.folders = {}  # folder name -> FolderSelection

    def name_of(self, folder):
        """The name a recording folder is saved under: its path inside the recordings folder."""
        return Path(folder).relative_to(self.recordings_folder).as_posix()

    def of(self, folder):
        """The selection of a recording folder, or None if it has none yet."""
        return self.folders.get(self.name_of(folder))

    def change_settings(self, settings):
        """Use new settings.

        Folders that were adjusted by hand keep their ROI and electrode; only
        their radius follows the new settings. All other folders are forgotten,
        so they are detected again with the new settings.
        """
        if settings == self.settings:
            return
        self.settings = settings
        self.folders = {name: s for name, s in self.folders.items() if s.is_manual}
        for selection in self.folders.values():
            selection.roi_radius_px = settings.roi_radius_px

    def save(self, path):
        """Write everything to a JSON file."""
        content = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "ema_version": __version__,
            "saved": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "recordings_folder": self.recordings_folder.as_posix(),
            "settings": self.settings.to_dict(),
            "folders": {name: self.folders[name].to_dict() for name in sorted(self.folders)},
        }
        # Write a complete new file first, so a crash can never leave half a file behind.
        temporary = Path(path).with_suffix(".tmp")
        temporary.write_text(json.dumps(content, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    @classmethod
    def load(cls, path):
        """Read a file written by `save`."""
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        if saved.get("format") != FORMAT:
            raise ValueError(f"{Path(path).name} is not an EMA ROI file.")
        if saved["format_version"] > FORMAT_VERSION:
            raise ValueError(f"{Path(path).name} was written by a newer version of EMA ({saved['ema_version']}).")
        selections = cls(saved["recordings_folder"], RoiSettings.from_dict(saved["settings"]))
        for name, folder in saved["folders"].items():
            selections.folders[name] = FolderSelection.from_dict(folder)
        return selections

    def export_table(self, path):
        """Write one row per folder to a CSV file that opens in Excel."""
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(
                ["folder", "roi_x", "roi_y", "roi_radius_px", "roi_source", "electrode_source",
                 "electrode_pixels", "peak_response_percent", "reviewed", "flagged_files"]
            )
            for name in sorted(self.folders):
                s = self.folders[name]
                flags = "; ".join(f"{file}: {reason}" if reason else file for file, reason in s.flagged_files.items())
                writer.writerow(
                    [name, *s.roi_center, s.roi_radius_px, s.roi_source, s.electrode_source,
                     int(s.electrode_mask.sum()), s.peak_response_percent, s.reviewed, flags]
                )


# ---------------------------------------------------------------------------
# Masks as text
# ---------------------------------------------------------------------------


def mask_runs(mask):
    """The runs of True pixels in each row of a mask, as (row, first column, last column)."""
    for row, line in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.concatenate(([False], line, [False]))))
        for first, after in zip(edges[::2], edges[1::2]):
            yield row, int(first), int(after) - 1


def mask_to_text(mask):
    """A mask as text, for example '59:0-34 60:0-36': in row 59, columns 0 to 34 are True."""
    return " ".join(f"{row}:{first}-{last}" for row, first, last in mask_runs(mask))


def text_to_mask(text, shape):
    """The mask written by `mask_to_text`, for an image of this shape (rows, columns)."""
    mask = np.zeros(shape, bool)
    for run in text.split():
        row, columns = run.split(":")
        first, last = columns.split("-")
        mask[int(row), int(first) : int(last) + 1] = True
    return mask
