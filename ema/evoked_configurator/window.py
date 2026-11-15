"""The Evoked Analysis Configurator: make, check and save protocols."""

from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..evoked import library
from ..evoked.measures import Measurement, measure
from ..evoked.protocol import Protocol, ProtocolError
from ..evoked.spatial import measure_spatial
from ..user_settings import remember, remembered
from .editors import PulsesEditor, RecordingsEditor
from .example import ExampleFolder
from .measure_editors import ComparisonsEditor, KineticsEditor, SpatialEditor
from .plot import TracePlot
from .spatial_plot import SpatialView
from .template_dialog import TemplateDialog
from .widgets import Units

TABS = ("1  Recordings", "2  Pulses and windows", "3  Kinetics", "4  Spatial", "5  Comparisons and summary")
SPATIAL_TAB = 3


class ConfiguratorWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, user_folder=None):
        super().__init__()
        self.setWindowTitle("EMA – Evoked Analysis Configurator")
        self.user_folder = user_folder  # where saved protocols go; None means the library's own folder
        self.units = Units()
        self.entry = None  # the library entry on show, or None for a protocol that was never saved
        self.protocol = None
        self.saved = None  # the protocol as last saved, to tell whether it changed
        self.example = None
        self.choices = []
        self.trace = None
        self.measurement = Measurement()
        self.spatial = None  # the spatial measures of the example recording, when they are needed

        self._build_window()
        self.entries = library.entries(self.user_folder)
        self.open_entry(0)
        folder = remembered("evoked_example_folder")
        if folder and Path(folder).is_dir():
            self.use_example_folder(Path(folder), remembered("evoked_roi_file") or None)
        else:
            self.plot.clear("Choose an example folder above to see the protocol on a real recording.")

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def _build_window(self):
        self.library_box = QComboBox()
        self.library_box.setMinimumWidth(260)
        self.library_box.activated.connect(self.choose_entry)
        buttons = {}
        for text, tip, action in (
            ("New…", "Make a new protocol from the template: a train of pulses and, if you want, a recovery pulse.", self.new_protocol),
            ("Save", "Save the changes. A built-in protocol is saved under a new name.", self.save),
            ("Save as…", "Save as a new protocol.", self.save_as),
            ("Delete", "Delete this protocol from the library.", self.delete),
            ("Import…", "Add a protocol file to the library.", self.import_protocol),
            ("Export…", "Save a copy of this protocol anywhere, e.g. to share it.", self.export),
        ):
            buttons[text] = QPushButton(text)
            buttons[text].setToolTip(tip)
            buttons[text].clicked.connect(action)
        self.delete_button = buttons["Delete"]
        self.state = QLabel()
        top = QHBoxLayout()
        top.addWidget(QLabel("Protocol:"))
        top.addWidget(self.library_box)
        for button in buttons.values():
            top.addWidget(button)
        top.addWidget(self.state, 1)

        self.editors = [RecordingsEditor(self.units), PulsesEditor(self.units), KineticsEditor(self.units),
                        SpatialEditor(self.units), ComparisonsEditor(self.units)]
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(False)
        for editor, title in zip(self.editors, TABS):
            self.tabs.addTab(editor, title)
            editor.changed.connect(self.protocol_changed)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.problems = QLabel()
        self.problems.setWordWrap(True)
        left = QWidget()
        left.setMinimumWidth(600)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.tabs, 1)
        left_layout.addWidget(self.problems)

        self.folder_label = QLabel("No example folder")
        self.folder_label.setMinimumWidth(40)
        self.folder_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        choose_folder = QPushButton("Example folder…")
        choose_folder.setToolTip("A folder of recordings to try the protocol on. Nothing is written into it.")
        choose_folder.clicked.connect(self.choose_example_folder)
        choose_roi = QPushButton("ROI file…")
        choose_roi.setToolTip("Use the ROI saved by ROI Selection (roi_selections.json) instead of finding it automatically.")
        choose_roi.clicked.connect(self.choose_roi_file)
        self.recording_box = QComboBox()
        self.recording_box.setMinimumWidth(170)
        self.recording_box.currentIndexChanged.connect(self.show_example)
        self.roi_label = QLabel()
        self.roi_label.setStyleSheet("color: gray")
        example_row = QHBoxLayout()
        example_row.addWidget(choose_folder)
        example_row.addWidget(self.folder_label, 1)
        example_row.addWidget(choose_roi)
        example_row.addWidget(QLabel("Recording:"))
        example_row.addWidget(self.recording_box)

        self.plot = TracePlot()
        self.plot.toolbar = NavigationToolbar2QT(self.plot, self, coordinates=False)
        self.plot.dragged.connect(self.window_dragged)
        self.plot.drag_finished.connect(lambda: self.protocol_changed(True))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Measure", "On the example", "Unit", "What it is"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        for column in (1, 2):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addLayout(example_row)
        right_layout.addWidget(self.roi_label)
        trace_page = QWidget()
        trace_layout = QVBoxLayout(trace_page)
        trace_layout.setContentsMargins(0, 0, 0, 0)
        trace_layout.addWidget(self.plot.toolbar)
        trace_layout.addWidget(self.plot, 1)
        self.spatial_view = SpatialView()
        self.spatial_view.pulse_chosen.connect(self.show_spatial)
        self.views = QStackedWidget()
        self.views.addWidget(trace_page)
        self.views.addWidget(self.spatial_view)
        right_layout.addWidget(self.views, 3)
        right_layout.addWidget(QLabel("<b>What the analysis will measure</b> (hover over a row for its definition)"))
        right_layout.addWidget(self.table, 2)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([620, 800])
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(main)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1450, screen.width() - 40), min(820, screen.height() - 60))

    # ------------------------------------------------------------------
    # The library
    # ------------------------------------------------------------------

    def fill_library(self):
        """List the library, with the protocol on show selected (or added at the end if it was never saved)."""
        self.entries = library.entries(self.user_folder)
        labels = [entry.label for entry in self.entries]
        index = next((i for i, e in enumerate(self.entries) if self.entry and e.path == self.entry.path), None)
        if index is None:
            labels.append(f"{self.protocol.name}  (not saved)")
            index = len(labels) - 1
        self.library_box.blockSignals(True)
        self.library_box.clear()
        self.library_box.addItems(labels)
        self.library_box.setCurrentIndex(index)
        self.library_box.blockSignals(False)

    @property
    def unsaved(self):
        return self.saved is None or self.protocol.to_dict() != self.saved

    def open_entry(self, index):
        entry = self.entries[index]
        try:
            protocol = entry.load()
        except (OSError, ProtocolError) as error:
            QMessageBox.warning(self, "Cannot open", f"{entry.path}\n\n{error}")
            return
        self.show_protocol(protocol, entry)

    def show_protocol(self, protocol, entry):
        self.protocol, self.entry = protocol, entry
        self.saved = protocol.to_dict() if entry else None
        self.units.frame_ms = protocol.sampling_interval_ms
        self.delete_button.setEnabled(entry is not None and not entry.built_in)
        self.fill_library()
        self.protocol_changed(True)

    def choose_entry(self, index):
        if index >= len(self.entries):
            return  # the unsaved protocol on show
        if self.entries[index] == self.entry or not self.may_discard():
            self.fill_library()
            return
        self.open_entry(index)

    def may_discard(self):
        """True if there are no unsaved changes, or the user saves or discards them."""
        if not self.unsaved:
            return True
        answer = QMessageBox.question(
            self, "Unsaved changes", f"Save the changes to {self.protocol.name}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if answer == QMessageBox.Save:
            return self.save()
        return answer == QMessageBox.Discard

    def ask_name(self, title, suggestion):
        """A protocol name the library does not use yet, or None if the user cancels."""
        while True:
            name, accepted = QInputDialog.getText(self, title, "Name of the protocol:", text=suggestion)
            name = name.strip()
            if not accepted or not name:
                return None
            if not library.is_taken(name, self.user_folder):
                return name
            QMessageBox.information(self, title, f"There is already a protocol called {name}. Choose another name.")
            suggestion = name

    def new_protocol(self):
        """Make a protocol from the template form."""
        if not self.may_discard():
            return
        dialog = TemplateDialog(self, "New protocol", self.protocol.sampling_interval_ms)
        if not dialog.exec_():
            return
        protocol = dialog.template().build()
        if library.is_taken(protocol.name, self.user_folder):
            name = self.ask_name("New protocol", f"{protocol.name} 2")
            if not name:
                return
            protocol.name = name
        self.show_protocol(protocol, None)

    def save(self):
        """Save into the library. True if it was saved."""
        if self.entry is None or self.entry.built_in:
            return self.save_as()
        if library.is_taken(self.protocol.name, self.user_folder, except_path=self.entry.path):
            QMessageBox.information(self, "Save", f"There is already a protocol called {self.protocol.name}. Change its name or use Save as….")
            return False
        return self._store(replacing=self.entry.path)

    def save_as(self):
        suggestion = self.protocol.name
        if library.is_taken(suggestion, self.user_folder):
            suggestion = f"{suggestion} copy"
        name = self.ask_name("Save as", suggestion)
        if not name:
            return False
        self.protocol.name = name
        return self._store(replacing=None)

    def _store(self, replacing):
        problems = self.protocol.problems()
        if problems:
            QMessageBox.warning(self, "Cannot save yet", "Please fix these first:\n\n• " + "\n• ".join(problems))
            return False
        try:
            path = library.save(self.protocol, self.user_folder, replacing)
        except OSError as error:
            QMessageBox.warning(self, "Cannot save", str(error))
            return False
        entry = next(e for e in library.entries(self.user_folder) if e.path == path)
        self.show_protocol(self.protocol, entry)
        self.statusBar().showMessage(f"Saved {path.name} in the protocol library.", 6000)
        return True

    def delete(self):
        if self.entry is None or self.entry.built_in:
            return
        answer = QMessageBox.question(self, "Delete", f"Delete the protocol {self.entry.name} from the library?\nThis cannot be undone.")
        if answer == QMessageBox.Yes:
            library.delete(self.entry)
            self.entries = library.entries(self.user_folder)
            self.open_entry(0)

    def import_protocol(self):
        if not self.may_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import a protocol", remembered("evoked_import_folder"), "Protocols (*.json)")
        if not path:
            return
        remember(evoked_import_folder=str(Path(path).parent))
        try:
            protocol = Protocol.load(path)
        except (OSError, ProtocolError) as error:
            QMessageBox.warning(self, "Cannot import", f"{path}\n\n{error}")
            return
        if library.is_taken(protocol.name, self.user_folder):
            name = self.ask_name("Import", f"{protocol.name} (imported)")
            if not name:
                return
            protocol.name = name
        self.show_protocol(protocol, None)
        self._store(replacing=None)

    def export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export the protocol", str(Path(remembered("evoked_import_folder") or Path.home()) / library.file_name(self.protocol.name)),
            "Protocols (*.json)",
        )
        if path:
            try:
                self.protocol.save(path)
            except OSError as error:
                QMessageBox.warning(self, "Cannot export", str(error))
                return
            self.statusBar().showMessage(f"Exported to {path}.", 6000)

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def protocol_changed(self, rebuild):
        """Something in the protocol changed. `rebuild` when the tabs and the example must be filled again."""
        if rebuild:
            for editor in self.editors:
                editor.show_protocol(self.protocol)
            self.fill_choices()
        else:
            self.show_example()
        self.show_state()

    def window_dragged(self):
        self.measurement = self.measure_example()
        self.plot.show_measurement(self.measurement)

    def tab_changed(self, index):
        """The Spatial tab shows the response maps; every other tab the trace."""
        self.views.setCurrentIndex(1 if index == SPATIAL_TAB else 0)
        if index == SPATIAL_TAB:
            self.show_spatial()

    @property
    def spatial_needed(self):
        return self.tabs.currentIndex() == SPATIAL_TAB or bool(self.protocol.spatial_measures or self.protocol.near_to_far)

    def measure_spatial(self):
        """The spatial measures of the example recording (and maps of the pulse shown on the Spatial tab)."""
        self.spatial = None
        if self.trace is None or not self.spatial_needed:
            return
        choice = self.choices[self.recording_box.currentIndex()]
        self.spatial_view.show_pulses([p.name for p in self.protocol.pulses])
        shown = [self.spatial_view.pulse] if self.spatial_view.pulse else []
        pulses = list(dict.fromkeys(self.protocol.spatial_pulses + shown))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            movie = self.example.movie(self.protocol, choice)
            self.spatial = measure_spatial(self.protocol, movie, self.example.center, self.example.electrode,
                                           self.measurement, choice.recording, pulses, self.spatial_view.wants_decay)
        except (OSError, ValueError, MemoryError) as error:
            self.spatial_view.clear(str(error))
        finally:
            QApplication.restoreOverrideCursor()

    def show_spatial(self):
        if self.tabs.currentIndex() != SPATIAL_TAB:
            return
        if self.example is None or self.trace is None:
            self.spatial_view.clear("Choose an example folder to see the response maps.")
            return
        self.measure_spatial()
        if self.spatial is not None:
            self.spatial_view.show_result(self.protocol, self.spatial, self.example.center, self.example.electrode)
        self.fill_table()

    def show_state(self):
        mark = "  –  changes not saved" if self.unsaved else ""
        self.state.setText(f"<span style='color:#b35c00'>{mark}</span>" if mark else "")
        problems = self.protocol.problems()
        lines = [f"<span style='color:#c1121f'>⚠ {problem}</span>" for problem in problems]
        lines += [f"<span style='color:#b35c00'>Example: {problem}</span>" for problem in self.measurement.problems]
        self.problems.setText("<br>".join(lines) if lines else "<span style='color:#1a7f37'>✓ The protocol is complete.</span>")
        self.fill_table()

    # ------------------------------------------------------------------
    # The example
    # ------------------------------------------------------------------

    def choose_example_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder of recordings", remembered("evoked_example_folder"))
        if folder:
            self.use_example_folder(Path(folder), remembered("evoked_roi_file") or None)

    def choose_roi_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose an ROI file", remembered("evoked_roi_file"), "ROI files (roi_selections.json);;All files (*.json)")
        if path and self.example is not None:
            self.use_example_folder(self.example.folder, path)
        elif path:
            remember(evoked_roi_file=path)

    def use_example_folder(self, folder, roi_file):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.example = ExampleFolder(folder, roi_file)
        except (OSError, ValueError) as error:
            self.example = None
            self.folder_label.setText(_short(folder))
            self.roi_label.setText(f"⚠ {error}")
            self.fill_choices()
            return
        finally:
            QApplication.restoreOverrideCursor()
        remember(evoked_example_folder=str(folder), evoked_roi_file=roi_file or "")
        self.folder_label.setText(_short(folder))
        self.folder_label.setToolTip(str(folder))
        self.roi_label.setText(self.example.roi_source)
        self.fill_choices()

    def fill_choices(self):
        """List the example recordings the protocol on show measures, keeping the one on show if it is still there."""
        current = self.recording_box.currentText()
        self.choices = self.example.choices(self.protocol) if self.example else []
        self.recording_box.blockSignals(True)
        self.recording_box.clear()
        for choice in self.choices:
            self.recording_box.addItem(choice.label + (f"  ({choice.missing})" if choice.missing else ""))
        index = next((i for i, c in enumerate(self.choices) if c.label == current.split("  (")[0]), 0)
        self.recording_box.setCurrentIndex(index if self.choices else -1)
        self.recording_box.blockSignals(False)
        self.show_example()

    def show_example(self, index=None):
        """Measure the example recording and draw it. The zoom stays when the same recording is shown again."""
        index = self.recording_box.currentIndex()
        if self.example is None or index < 0:
            self.trace, self.measurement, self.spatial = None, Measurement(), None
            if self.example is not None:
                self.plot.clear("The protocol measures none of the recordings in this folder.")
            self.show_state()
            return
        choice = self.choices[index]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.trace = self.example.trace(self.protocol, choice)
        except (OSError, ValueError) as error:
            self.trace, self.measurement, self.spatial = None, Measurement(), None
            self.plot.clear(str(error))
            self.show_state()
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.measurement = self.measure_example()
        same = self.plot.protocol is not None and self.plot.title == (choice.label, self.protocol.trace)
        self.plot.show_trace(self.protocol, self.trace, choice.recording, self.measurement, choice.label, keep_view=same)
        if self.tabs.currentIndex() == SPATIAL_TAB:
            self.show_spatial()
        else:
            self.measure_spatial()
        self.show_state()

    def measure_example(self):
        if self.trace is None:
            return Measurement()
        recording = self.choices[self.recording_box.currentIndex()].recording
        return measure(self.protocol, self.trace, recording)

    def fill_table(self):
        measures = self.protocol.measures()
        values = {**self.measurement.values, **(self.spatial.values if self.spatial else {})}
        self.table.setRowCount(0)
        part = None
        for item in measures:
            if item.per != part:
                part = item.per
                self._add_heading("Per recording" if part == "recording" else "Per slice (all recordings of a folder; not shown on one example)")
            value = values.get(item.name) if part == "recording" else None
            text = "" if value is None else ("–" if not np.isfinite(value) else f"{value:.4g}")
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, cell in enumerate((item.name, text, item.unit, item.explanation)):
                entry = QTableWidgetItem(cell)
                entry.setToolTip(item.explanation)
                if column == 1:
                    entry.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, column, entry)
        widest = max((self.table.fontMetrics().horizontalAdvance(m.name) for m in measures), default=80)
        self.table.setColumnWidth(0, widest + 24)

    def _add_heading(self, text):
        row = self.table.rowCount()
        self.table.insertRow(row)
        cell = QTableWidgetItem(text)
        font = QFont()
        font.setBold(True)
        cell.setFont(font)
        cell.setBackground(QColor("#eef2f7"))
        self.table.setItem(row, 0, cell)
        self.table.setSpan(row, 0, 1, 4)

    def closeEvent(self, event):  # noqa: N802 (Qt's name)
        if not self.may_discard():
            event.ignore()
            return
        self.closed.emit()
        super().closeEvent(event)


def _short(folder):
    """The last three parts of a folder path, which is what tells recording folders apart."""
    parts = Path(folder).parts
    return str(Path(*parts[-3:])) if len(parts) > 3 else str(folder)
