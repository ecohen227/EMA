"""Spontaneous Event Analysis: search the unstimulated recordings of every folder under a recordings folder.

The window is the one both analyses share (ema/analysis_window.py); this is
what the spontaneous-event analysis brings to it.
"""

from functools import partial

from ..analysis_window import AnalysisWindow, Kind
from ..spontaneous.analysis import Analysis, Recordings, plan, run
from ..spontaneous.presets import LIBRARY
from ..spontaneous.workbook import PER_EVENT, PER_SLICE, write_workbooks


def describe(detector):
    """One line about a detector's measures, and what is wrong with it."""
    s = detector.settings
    text = (f"{len(detector.event_measures)} measures per event, {len(detector.recording_measures)} per recording, "
            f"{len(detector.slice_columns())} per slice. Events at least {s.event_z:g} × the noise, pixels pooled over "
            f"{s.blur_um:g} µm.")
    return text, detector.problems()


def spontaneous(workers=None):
    """What the spontaneous-event analysis brings to the window; `workers` sets how many recordings are searched at once."""
    return Kind(
        title="EMA – Spontaneous Event Analysis",
        configurator="Spontaneous Event Configurator",
        key="spontaneous_analysis",
        analysis=Analysis,
        tables=(PER_EVENT, PER_SLICE),
        library=LIBRARY,
        describe=describe,
        plan=plan,
        run=partial(run, workers=workers),
        write=write_workbooks,
        source=Recordings,
    )


class SpontaneousAnalysisWindow(AnalysisWindow):
    def __init__(self, user_folder=None, workers=None):
        super().__init__(spontaneous(workers), user_folder)
