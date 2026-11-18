"""The Exclusions tab: which slices are left out of the tables.

Each exclusion is a small form that reads as a sentence: the value of a slice
(such as the spread of B1 over its recordings), and when it leaves the slice
out (such as above Q3 + 1.5 × IQR of all slices). Below the exclusions, they
can be tried on the results of an earlier analysis, to see which slices they
would leave out before anything is run.
"""

import math
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ..evoked.analysis import FILE_NAME, Analysis
from ..evoked.exclusions import judge, left_out
from ..evoked.protocol import (
    ABOVE,
    ALL_RECORDINGS,
    AMONG_ALL,
    AMONG_GROUP,
    BELOW,
    BY_CONDITION,
    BY_FILES,
    DEVIATIONS,
    EITHER_SIDE,
    HIGH_SIDE,
    INTERQUARTILE,
    LARGEST,
    LOW_SIDE,
    MEAN,
    MEDIAN,
    RANGE,
    SMALLEST,
    SPREAD_OF_LARGEST,
    SPREAD_OF_SMALLEST,
    VARIATION,
    Exclusion,
    file_patterns,
)
from ..excel import group_name, slices
from ..user_settings import remember, remembered
from ..widgets import ERROR_COLOUR, coloured
from .editors import Editor
from .widgets import choice_box, hint, remove_button, row_of

STATISTIC_CHOICES = [
    ("spread: (largest − smallest) ÷ largest × 100", SPREAD_OF_LARGEST),
    ("spread: (largest − smallest) ÷ smallest × 100", SPREAD_OF_SMALLEST),
    ("range: largest − smallest", RANGE),
    ("coefficient of variation: SD ÷ mean × 100", VARIATION),
    ("mean", MEAN),
    ("median", MEDIAN),
    ("smallest value", SMALLEST),
    ("largest value", LARGEST),
]
TEST_CHOICES = [
    ("outside Q1 − k·IQR to Q3 + k·IQR", INTERQUARTILE),
    ("more than k standard deviations from the mean", DEVIATIONS),
    ("above a limit", ABOVE),
    ("below a limit", BELOW),
]
SIDE_CHOICES = [("too high or too low", EITHER_SIDE), ("too high only", HIGH_SIDE), ("too low only", LOW_SIDE)]
AMONG_CHOICES = [("all slices", AMONG_ALL), ("the slices of its group", AMONG_GROUP)]
RECORDING_CHOICES = [("all its recordings", ALL_RECORDINGS), ("its recordings with a condition from", BY_CONDITION),
                     ("its recordings named", BY_FILES)]


class ExclusionsEditor(Editor):
    def __init__(self, units):
        super().__init__(units)
        self.list = QWidget()
        self.list_layout = QGridLayout(self.list)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        add = QPushButton("Add exclusion")
        add.setToolTip("Leave out the slices whose baseline B1 changes unusually much between their recordings; change "
                       "it to any other rule.")
        add.clicked.connect(self.add_exclusion)
        self.box(
            "Leave out slices",
            self.list,
            row_of(add),
            explanation="A slice (one recording folder) is left out of both files, Evoked per recording.xlsx and Evoked "
                        "per slice.xlsx, when any exclusion below says so. Each exclusion makes one value per slice from "
                        "one measure of its recordings, e.g. how much B1 changes between them, and compares it with the "
                        "other slices (their quartiles or mean, worked out before any slice is left out) or with a fixed "
                        "limit. Both files get an Exclusions sheet with every slice's value. Changing the exclusions "
                        "measures nothing again: running the analysis only writes the tables again.",
        )

        choose = QPushButton("Results of an analysis…")
        choose.setToolTip(f"Choose the output folder of an evoked analysis (it holds {FILE_NAME}).")
        choose.clicked.connect(self.choose_results)
        self.results_label = hint("No results chosen.")
        self.results_label.setWordWrap(True)
        self.verdicts = QTableWidget(0, 5)
        self.verdicts.setHorizontalHeaderLabels(["Folder", "Exclusion", "Value", "Kept from … to", "Left out"])
        self.verdicts.verticalHeader().setVisible(False)
        self.verdicts.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verdicts.setMinimumHeight(220)
        header = self.verdicts.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.box("Try them", row_of(choose, self.results_label), self.verdicts,
                 explanation="See which slices these exclusions would leave out, using the results kept by an earlier "
                             "run of the evoked analysis. Its groups are the ones chosen in that analysis.")
        self.content.addStretch()
        self.analysis, self.results_name = None, ""
        self.sentences = {}  # id of an Exclusion -> the label that says it in words
        folder = remembered("evoked_exclusion_results")
        if folder:
            self.use_results(Path(folder), quiet=True)

    # ------------------------------------------------------------------
    # The exclusions
    # ------------------------------------------------------------------

    def fill(self):
        p = self.protocol
        while self.list_layout.count():
            widget = self.list_layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.sentences = {}
        measures = [(m.name, m.name) for m in p.recording_measures()]
        units = {m.name: m.unit for m in p.recording_measures()}
        if not p.exclusions:
            self.list_layout.addWidget(hint("No exclusions: every slice is in the tables."), 0, 0)
        for number, exclusion in enumerate(p.exclusions, 1):
            self.list_layout.addWidget(self._form(number, exclusion, measures, units), number - 1, 0)
        self.try_them()

    def _form(self, number, exclusion, measures, units):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        grid = QGridLayout(frame)
        grid.setColumnStretch(2, 1)
        unit = exclusion.unit(units.get(exclusion.measure, ""))

        title = QLabel(f"<b>Exclusion {number}</b>")
        grid.addWidget(title, 0, 0)
        grid.addWidget(remove_button(lambda _=False, e=exclusion: self._remove(e), f"exclusion {number}"), 0, 3,
                       Qt.AlignRight)

        statistic = choice_box(STATISTIC_CHOICES, exclusion.statistic, lambda v, e=exclusion: self._set(e, statistic=v))
        measure = choice_box(measures, exclusion.measure, lambda v, e=exclusion: self._set(e, measure=v))
        grid.addWidget(QLabel("Value of a slice:"), 1, 0)
        grid.addWidget(row_of(statistic, "of", measure), 1, 1, 1, 3)

        recordings = choice_box(RECORDING_CHOICES, exclusion.by, lambda v, e=exclusion: self._set(e, by=v))
        which = [recordings]
        if exclusion.by == BY_CONDITION:
            low, high = QDoubleSpinBox(), QDoubleSpinBox()
            for box, value in ((low, exclusion.low), (high, exclusion.high)):
                box.setRange(-1e6, 1e6)
                box.setDecimals(1)
                box.setKeyboardTracking(False)
                box.setSuffix(f" {self.protocol.condition_unit}" if self.protocol.condition_unit else "")
                box.setValue(value)
            for box in (low, high):
                box.valueChanged.connect(lambda _=0, e=exclusion, a=low, b=high: self._set(e, False, low=a.value(),
                                                                                            high=b.value()))
            which += [low, "to", high]
        elif exclusion.by == BY_FILES:
            files = QLineEdit(", ".join(exclusion.files))
            files.setMinimumWidth(160)
            files.setPlaceholderText("hi*   or   hi1, hi2")
            files.setToolTip("File names separated by commas, with or without .tif. * stands for any characters and ? "
                             "for one; upper and lower case alike.")
            files.editingFinished.connect(lambda e=exclusion, w=files: self._set(e, files=file_patterns(w.text())))
            which.append(files)
        grid.addWidget(QLabel("Over:"), 2, 0)
        grid.addWidget(row_of(*which), 2, 1, 1, 3)

        test = choice_box(TEST_CHOICES, exclusion.test, lambda v, e=exclusion: self._set(e, test=v))
        number_box = QDoubleSpinBox()
        number_box.setKeyboardTracking(False)
        number_box.setDecimals(2 if exclusion.relative else 3)
        if exclusion.relative:
            number_box.setRange(0, 100)
            number_box.setSingleStep(0.5)
            number_box.setPrefix("k = ")
            number_box.setValue(exclusion.factor)
            number_box.setToolTip("1.5 is the usual choice for outliers (Tukey's fences); 0 leaves out every slice "
                                  "outside the interquartile range itself, half of them.")
            number_box.valueChanged.connect(lambda v, e=exclusion: self._set(e, False, factor=v))
            side = choice_box(SIDE_CHOICES, exclusion.side, lambda v, e=exclusion: self._set(e, side=v))
            among = choice_box(AMONG_CHOICES, exclusion.among, lambda v, e=exclusion: self._set(e, among=v))
            among.setToolTip("The groups are the ones chosen in Evoked Analysis, such as WT CTRL and HET CTRL.")
            rule = [test, number_box]
            grid.addWidget(QLabel("Unusual:"), 4, 0)
            grid.addWidget(row_of(side, "among", among), 4, 1, 1, 3)
        else:
            number_box.setRange(-1e9, 1e9)
            number_box.setValue(exclusion.limit)
            number_box.setSuffix(f" {unit}" if unit and unit != "ratio" else "")
            number_box.valueChanged.connect(lambda v, e=exclusion: self._set(e, False, limit=v))
            rule = [test, number_box]
        grid.addWidget(QLabel("Left out when it is:"), 3, 0)
        grid.addWidget(row_of(*rule), 3, 1, 1, 3)

        sentence = hint()
        sentence.setWordWrap(True)
        self.sentences[id(exclusion)] = (sentence, unit)
        self._say(exclusion)
        grid.addWidget(sentence, 5, 0, 1, 4)
        return frame

    def _say(self, exclusion):
        sentence, unit = self.sentences[id(exclusion)]
        sentence.setText(f"Leaves out a slice when {exclusion.value_text(self.protocol.condition_label)} is "
                         f"{exclusion.test_text(unit)}.")

    def add_exclusion(self):
        p = self.protocol
        names = [m.name for m in p.recording_measures()]
        if not names:
            return
        first_baseline = next(iter(p.baselines), None)
        p.exclusions.append(Exclusion(first_baseline if first_baseline in names else names[0]))
        self.changed.emit(True)

    def _set(self, exclusion, rebuild=True, **changes):
        """Change an exclusion. A number typed or stepped changes only its sentence and the trial, so the box keeps
        the focus; a choice rebuilds the form, whose boxes depend on it."""
        for attribute, value in changes.items():
            setattr(exclusion, attribute, value)
        if rebuild:
            self.changed.emit(True)
            return
        self._say(exclusion)
        self.try_them()
        self.changed.emit(False)

    def _remove(self, exclusion):
        self.protocol.exclusions.remove(exclusion)
        self.changed.emit(True)

    # ------------------------------------------------------------------
    # Trying them on earlier results
    # ------------------------------------------------------------------

    def choose_results(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose the output folder of an evoked analysis",
                                                  remembered("evoked_exclusion_results") or remembered("evoked_analysis_output"))
        if folder:
            self.use_results(Path(folder))

    def use_results(self, folder, quiet=False):
        try:
            self.analysis = Analysis.load(folder / FILE_NAME)
        except (OSError, ValueError) as error:
            self.analysis = None
            if not quiet:
                self.results_label.setText(coloured(f"⚠ {folder.name} holds no results that can be read: {error}",
                                                    ERROR_COLOUR))
            self.try_them()
            return
        remember(evoked_exclusion_results=str(folder))
        self.results_name = folder.name
        self.results_label.setToolTip(str(folder))
        self.try_them()

    def try_them(self):
        """Fill the table with what the exclusions would do to the chosen results."""
        self.verdicts.setRowCount(0)
        if self.analysis is None or self.protocol is None:
            return
        found = slices(self.analysis)
        verdicts = judge(self.protocol, found, lambda item: group_name(self.analysis, item.group))
        out = left_out(verdicts)
        self.results_label.setText(f"{self.results_name}: {len(out)} of {len(found)} slices would be left out."
                                   if self.protocol.exclusions else f"{self.results_name}: {len(found)} slices.")
        # The slices left out first, then the others; within each, in the order of the tables
        for verdict in sorted(verdicts, key=lambda v: v.slice.key not in out):
            row = self.verdicts.rowCount()
            self.verdicts.insertRow(row)
            kept = "–" if math.isnan(verdict.low) else f"{_text(verdict.low)} to {_text(verdict.high)}"
            left = "yes" if verdict.left_out else ("not tested" if verdict.why else "")
            for column, text in enumerate((verdict.slice.result.name, str(verdict.number), _text(verdict.value), kept, left)):
                item = QTableWidgetItem(text)
                item.setToolTip(verdict.why or verdict.slice.result.name)
                if column in (2, 3):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.verdicts.setItem(row, column, item)


def _text(value):
    if math.isnan(value):
        return "–"
    if math.isinf(value):
        return "−∞" if value < 0 else "∞"
    return f"{value:.4g}"
