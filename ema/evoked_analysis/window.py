"""Evoked Analysis: measure the recordings of every folder in an ROI file with a protocol, and write the tables.

The window is the one both analyses share (ema/analysis_window.py); this is
what the evoked analysis brings to it.
"""

from ..analysis_window import AnalysisWindow as SharedWindow
from ..analysis_window import Kind
from ..evoked import library
from ..evoked.analysis import FILE_NAME, Analysis, plan, run
from ..evoked.protocol import Protocol
from ..evoked.workbook import PER_RECORDING, PER_SLICE, write_workbooks


def describe(protocol):
    """One line about a protocol's measures, and what is wrong with it."""
    measures = protocol.measures()
    per_slice = sum(m.per == "slice" for m in measures)
    problems = protocol.problems()
    if not per_slice:
        problems.append("No per-slice measures: the per-slice file will only list the slices.")
    return f"{len(measures) - per_slice} measures per recording, {per_slice} per slice.", problems


EVOKED = Kind(
    title="EMA – Evoked Analysis",
    method="protocol",
    configurator="Evoked Analysis Configurator",
    key="evoked_analysis",
    analysis=Analysis,
    file_name=FILE_NAME,
    tables=(PER_RECORDING, PER_SLICE),
    entries=lambda folder: [(entry.label, entry.path) for entry in library.entries(folder)],
    load=Protocol.load,
    describe=describe,
    plan=plan,
    run=run,
    write=write_workbooks,
)


class AnalysisWindow(SharedWindow):
    def __init__(self, user_folder=None):
        super().__init__(EVOKED, user_folder)
