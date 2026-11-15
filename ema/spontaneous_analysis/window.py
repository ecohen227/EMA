"""Spontaneous Event Analysis: search the unstimulated recordings of every folder under a recordings folder.

The window is the one both analyses share (ema/analysis_window.py); this is
what the spontaneous-event analysis brings to it.
"""

from functools import partial

from ..analysis_window import AnalysisWindow as SharedWindow
from ..analysis_window import Kind
from ..spontaneous import detector as library
from ..spontaneous.analysis import FILE_NAME, Analysis, Recordings, plan, run
from ..spontaneous.detector import Detector
from ..spontaneous.workbook import PER_EVENT, PER_SLICE, slice_measures, write_workbooks


def describe(detector):
    """One line about a detector's measures, and what is wrong with it."""
    per_slice = len(slice_measures(detector))
    text = (f"{len(detector.event_measures)} measures per event, {len(detector.recording_measures)} per recording, "
            f"{per_slice} per slice. Events at z ≥ {detector.settings.event_z:g}, filter σ {detector.settings.blur_um:g} µm.")
    return text, detector.problems()


def spontaneous(workers=None):
    """What the spontaneous-event analysis brings to the window; `workers` sets how many recordings are searched at once."""
    return Kind(
        title="EMA – Spontaneous Event Analysis",
        method="detector",
        configurator="Spontaneous Event Configurator",
        key="spontaneous_analysis",
        analysis=Analysis,
        file_name=FILE_NAME,
        tables=(PER_EVENT, PER_SLICE),
        entries=lambda folder: [(entry.label, entry.path) for entry in library.entries(folder)],
        load=Detector.load,
        describe=describe,
        plan=plan,
        run=partial(run, workers=workers),
        write=write_workbooks,
        source=Recordings,
    )


class SpontaneousAnalysisWindow(SharedWindow):
    def __init__(self, user_folder=None, workers=None):
        super().__init__(spontaneous(workers), user_folder)
