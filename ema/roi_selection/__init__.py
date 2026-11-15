"""ROI Selection: find the ROI and the electrode of every recording folder, and let the user correct them.

To read the selections from another package or a script::

    from ema.roi_selection import Selections

    selections = Selections.load("my_output_folder/roi_selections.json")
    for name, selection in selections.folders.items():
        print(name, selection.roi_center, selection.roi_radius_px)
"""

from .detection import (
    Detection,
    detect,
    detect_folder,
    find_electrode,
    find_roi_center,
    mean_recording,
    response_map,
    roi_mask,
    roi_trace,
)
from .selections import FILE_NAME, FolderSelection, Selections
from .settings import RoiSettings

__all__ = [
    "Detection",
    "FILE_NAME",
    "FolderSelection",
    "RoiSettings",
    "Selections",
    "detect",
    "detect_folder",
    "find_electrode",
    "find_roi_center",
    "mean_recording",
    "response_map",
    "roi_mask",
    "roi_trace",
]
