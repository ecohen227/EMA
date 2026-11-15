"""Example traces for the configurator: the ROI trace of real recordings, measured with the protocol on show."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..evoked.protocol import EVERY, RATIO, Window
from ..evoked.traces import combine, correction_window, find_partner, make_trace
from ..recordings import list_recordings, load_stack
from ..roi_selection import RoiSettings, Selections, detect_folder, roi_mask


@dataclass
class Choice:
    """A recording that can be shown: its label, its file(s) and its listed recording (if any)."""

    label: str
    file: Path
    unstimulated: Path = None
    recording: object = None  # the protocol's Recording, for listed recordings
    missing: str = ""  # why it cannot be shown, if it cannot


class ExampleFolder:
    """One recording folder, its ROI, and the ROI traces of its recordings.

    The ROI (its centre and the electrode mask too) comes from an ROI file
    made by ROI Selection when that file covers the folder, and is found
    automatically otherwise.
    """

    def __init__(self, folder, roi_file=None):
        self.folder = Path(folder)
        self.paths = list_recordings(self.folder)
        self.times = {}  # time stamps of the recordings, by path
        self.roi_source = ""
        self.center = self.electrode = None
        self.mask = self._find_roi(roi_file)
        self._trace = lru_cache(maxsize=32)(self._roi_trace)
        self._stack = lru_cache(maxsize=4)(load_stack)
        self._movie = lru_cache(maxsize=2)(self._make_movie)

    def _find_roi(self, roi_file):
        if roi_file:
            try:
                selection = Selections.load(roi_file).of(self.folder)
            except (OSError, ValueError, KeyError):
                selection = None
            if selection is not None:
                self.center, self.electrode = selection.roi_center, selection.electrode_mask
                x, y = selection.roi_center
                self.roi_source = f"ROI from {Path(roi_file).name}: centre ({x}, {y}), radius {selection.roi_radius_px:g} px"
                return selection.roi_mask()
            self.roi_source = f"{Path(roi_file).name} has no ROI for this folder, so it was found automatically. "
        settings = RoiSettings()
        detection = detect_folder(self.folder, settings)
        self.center, self.electrode = detection.center, detection.electrode
        x, y = detection.center
        self.roi_source += f"ROI found automatically: centre ({x}, {y}), radius {settings.roi_radius_px} px"
        return roi_mask(detection.response.shape, detection.center, settings.roi_radius_px)

    def _roi_trace(self, path):
        stack = self._stack(path)
        if stack.shape[1:] != self.mask.shape:
            raise ValueError(f"{path.name} has another image size than the rest of the folder.")
        return stack[:, self.mask].mean(axis=1)

    def choices(self, protocol):
        """The recordings of this folder that the protocol measures, each with its unstimulated partner."""
        if protocol.selection == EVERY:
            return [self._choice(protocol, path) for path in protocol.measured_files(self.paths)]
        names = {path.name.lower(): path for path in self.paths}
        found = []
        for recording in protocol.recordings:
            file = names.get(recording.file.lower())
            if file is None:
                found.append(Choice(recording.file, None, None, recording, f"{recording.file} is not in this folder."))
            else:
                found.append(self._choice(protocol, file, recording))
        return found

    def _choice(self, protocol, path, recording=None):
        partner, missing = find_partner(protocol, path, self.paths, recording, self.times)
        if partner is None:
            return Choice(path.name, path, None, recording, missing)
        link = "÷" if protocol.trace == RATIO else "corrected with"
        return Choice(f"{path.name} {link} {partner.name}", path, partner, recording)

    def trace(self, protocol, choice):
        """The trace the protocol measures for a recording (see ema.evoked.traces)."""
        self._check(choice)
        partner = self._trace(choice.unstimulated) if choice.unstimulated is not None else None
        try:
            return make_trace(protocol, self._trace(choice.file), partner, choice.recording)
        except ValueError as error:
            raise ValueError(f"{self._names(choice)}: {error}") from error

    def movie(self, protocol, choice):
        """The signal of every pixel the protocol measures, made like the trace but pixel by pixel."""
        self._check(choice)
        if choice.unstimulated is None:
            return self._movie(choice.file, None, False, None)
        window = None if protocol.trace == RATIO else correction_window(protocol, choice.recording)
        window = None if window is None else (window.start, window.end)
        try:
            return self._movie(choice.file, choice.unstimulated, protocol.trace == RATIO, window)
        except ValueError as error:
            raise ValueError(f"{self._names(choice)}: {error}") from error

    def _make_movie(self, file, partner, ratio, window):
        movie = self._stack(file).astype(np.float32)
        if partner is None:
            return movie
        background = np.maximum(self._stack(partner).astype(np.float32), 1)
        return combine(movie, background, ratio, None if window is None else Window(*window))

    def _check(self, choice):
        if choice.missing:
            raise ValueError(choice.missing)

    @staticmethod
    def _names(choice):
        return choice.file.name + (f" and {choice.unstimulated.name}" if choice.unstimulated else "")
