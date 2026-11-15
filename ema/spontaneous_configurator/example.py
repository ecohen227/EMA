"""The example folder of the spontaneous-event configurator: its unstimulated recordings, release centre and electrode."""

from functools import lru_cache
from pathlib import Path

import numpy as np

from ..recordings import list_recordings, load_stack
from ..roi_selection import RoiSettings, Selections, detect_folder


class ExampleFolder:
    """A folder of recordings with the release centre (ROI centre) and the electrode mask the detector needs.

    Both come from an ROI file made by ROI Selection when it covers the
    folder, otherwise they are found automatically from the folder's
    stimulated recordings. A folder without stimulated recordings gets the
    image centre and no electrode.
    """

    def __init__(self, folder, roi_file=None):
        self.folder = Path(folder)
        self.paths = list_recordings(self.folder)
        self.center, self.electrode, self.source = None, None, ""
        self._find_roi(roi_file)
        self.stack = lru_cache(maxsize=2)(load_stack)

    def _find_roi(self, roi_file):
        if roi_file:
            try:
                selection = Selections.load(roi_file).of(self.folder)
            except (OSError, ValueError, KeyError):
                selection = None
            if selection is not None:
                self.center, self.electrode = tuple(selection.roi_center), selection.electrode_mask
                self.source = f"Release centre and electrode from {Path(roi_file).name}."
                return
        try:
            detection = detect_folder(self.folder, RoiSettings())
        except (OSError, ValueError):
            shape = load_stack(self.paths[0]).shape[1:] if self.paths else (128, 128)
            self.center, self.electrode = (shape[1] // 2, shape[0] // 2), np.zeros(shape, bool)
            self.source = "No ROI file for this folder and no stimulated recording: the image centre is used, without electrode."
            return
        self.center, self.electrode = tuple(detection.center), detection.electrode
        self.source = "Release centre and electrode found automatically (choose an ROI file to use reviewed ones)."
