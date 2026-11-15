"""The Spontaneous Event Configurator: make, check and save detectors, tried on an example recording."""

from dataclasses import fields, replace
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..spontaneous import detector as library
from ..spontaneous.detection import detect
from ..spontaneous.detector import Detector, DetectorError
from ..spontaneous.measures import EVENT, RECORDING, SLICE, STATISTICS, event_trace, measure_events, measure_recording, peak_map
from ..spontaneous.settings import GROUPS, DetectorSettings
from ..user_settings import remember, remembered
from .example import ExampleFolder
from .settings_form import SettingsForm

MEASURING = {f.name for f in fields(DetectorSettings) if f.metadata["group"] == "Measuring"}


def _grey(text=""):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray")
    return label


def _format(value):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "–"
    if isinstance(value, (int, np.integer)):
        return str(value)
    return f"{value:.3g}" if abs(value) < 1000 else f"{value:.0f}"


class SearchWorker(QThread):
    """Searches the example recording in the background, so the window stays responsive."""

    def __init__(self, stack, electrode, settings, center):
        super().__init__()
        self.args = (stack, electrode, settings, center)
        self.detection = self.events = self.error = None

    def run(self):
        stack, electrode, settings, center = self.args
        try:
            self.detection = detect(stack, electrode, settings)
            self.events = measure_events(self.detection, settings, center, electrode)
        except (ValueError, MemoryError, np.linalg.LinAlgError) as error:
            self.error = error


class Checklist(QWidget):
    """Tick boxes for measures, in groups, with All and None."""

    changed = pyqtSignal()

    def __init__(self, measures):
        super().__init__()
        self.boxes = {}
        layout = QVBoxLayout(self)
        group = None
        for measure in measures:
            if measure.group != group:
                group = measure.group
                layout.addWidget(QLabel(f"<b>{group}</b>"))
            box = QCheckBox(f"{measure.key}  ({measure.unit})")
            box.setToolTip(measure.explanation)
            box.toggled.connect(self.changed)
            layout.addWidget(box)
            self.boxes[measure.key] = box
        buttons = QHBoxLayout()
        for text, on in (("All", True), ("None", False)):
            button = QPushButton(text)
            button.clicked.connect(lambda _, value=on: self.set_all(value))
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()

    def set_all(self, on):
        for box in self.boxes.values():
            box.blockSignals(True)
            box.setChecked(on)
            box.blockSignals(False)
        self.changed.emit()

    def show_chosen(self, keys):
        for key, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(key in keys)
            box.blockSignals(False)

    def chosen(self):
        return [key for key, box in self.boxes.items() if box.isChecked()]


def _scrolled(widget):
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    return area


class SpontaneousConfiguratorWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, user_folder=None):
        super().__init__()
        self.setWindowTitle("EMA – Spontaneous Event Configurator")
        self.user_folder = user_folder  # where saved detectors go; None means the library's own folder
        self.entry = None
        self.detector = None
        self.saved = None
        self.example = None
        self.detection = self.events = None
        self.searched_with = None  # the settings the example was searched with
        self.worker = None
        self.search_again = False
        self.searched_name = ""
        self.selected = 0
        self._build_window()
        self.entries = library.entries(self.user_folder)
        self.open_entry(0)
        folder = remembered("spontaneous_example_folder")
        if folder and Path(folder).is_dir():
            self.use_example_folder(Path(folder), remembered("spontaneous_roi_file") or None)

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def _build_window(self):
        self.library_box = QComboBox()
        self.library_box.setMinimumWidth(240)
        self.library_box.activated.connect(lambda index: self.open_entry(index))
        top = QHBoxLayout()
        top.addWidget(QLabel("Detector:"))
        top.addWidget(self.library_box)
        for text, tip, action in (
            ("Save", "Save the changes. A built-in detector is saved under a new name.", self.save),
            ("Save as…", "Save as a new detector.", self.save_as),
            ("Delete", "Delete this detector from the library.", self.delete),
            ("Import…", "Add a detector file to the library.", self.import_detector),
            ("Export…", "Save a copy of this detector anywhere, e.g. to share it.", self.export),
        ):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(action)
            top.addWidget(button)
            if text == "Delete":
                self.delete_button = button
        self.state = QLabel()
        top.addWidget(self.state, 1)

        self.description = QLineEdit()
        self.description.setPlaceholderText("What this detector is for")
        self.description.editingFinished.connect(self.edited)
        self.skip_words = QLineEdit()
        self.skip_words.setToolTip("Unstimulated recordings (named 'no' and a number) with one of these words in their name "
                                   "are not searched, e.g. 'no1 red.tif'.")
        self.skip_words.editingFinished.connect(self.edited)
        self.form = SettingsForm(DetectorSettings, GROUPS)
        self.form.changed.connect(self.setting_changed)
        defaults = QPushButton("Restore the defaults")
        defaults.setToolTip("Every setting back to detector v5's value.")
        defaults.clicked.connect(lambda: (self.form.show_settings(DetectorSettings()), self.setting_changed("")))
        detector_page = QWidget()
        page = QVBoxLayout(detector_page)
        about = QFormLayout()
        about.addRow("Description:", self.description)
        about.addRow("Skip recordings with:", self.skip_words)
        page.addLayout(about)
        page.addWidget(_grey("The settings of detector v5 are the defaults. Hover over a setting for what it does; a closed "
                             "section says how many of its settings differ from the defaults."))
        page.addWidget(self.form)
        page.addWidget(defaults)
        page.addStretch()

        self.event_list = Checklist(EVENT)
        self.event_list.changed.connect(self.measures_changed)
        self.recording_list = Checklist(RECORDING)
        self.recording_list.changed.connect(self.measures_changed)
        self.slice_list = Checklist(SLICE)
        self.slice_list.changed.connect(self.measures_changed)
        self.summary_list = Checklist(EVENT)
        self.summary_list.changed.connect(self.measures_changed)
        self.statistic_boxes = {}
        statistics = QHBoxLayout()
        statistics.addWidget(QLabel("Summarised by their:"))
        for statistic in STATISTICS:
            box = QCheckBox(statistic)
            box.toggled.connect(self.measures_changed)
            statistics.addWidget(box)
            self.statistic_boxes[statistic] = box
        statistics.addStretch()
        slice_page = QWidget()
        grid = QGridLayout(slice_page)
        grid.addWidget(QLabel("<b>Per recording</b>"), 0, 0)
        grid.addWidget(self.recording_list, 1, 0)
        grid.addWidget(QLabel("<b>Per slice</b> (all searched recordings of a folder)"), 0, 1)
        grid.addWidget(self.slice_list, 1, 1)
        summaries = QWidget()
        summary_layout = QVBoxLayout(summaries)
        summary_layout.addWidget(QLabel("<b>Per slice: event measures summarised</b>"))
        summary_layout.addLayout(statistics)
        summary_layout.addWidget(self.summary_list)
        grid.addWidget(summaries, 2, 0, 1, 2)

        self.tabs = QTabWidget()
        self.tabs.addTab(_scrolled(detector_page), "1  Detector")
        self.tabs.addTab(_scrolled(self.event_list), "2  Per event")
        self.tabs.addTab(_scrolled(slice_page), "3  Per recording and slice")
        self.problems = QLabel()
        self.problems.setWordWrap(True)
        left = QWidget()
        left.setMinimumWidth(460)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.tabs, 1)
        left_layout.addWidget(self.problems)

        choose_folder = QPushButton("Example folder…")
        choose_folder.setToolTip("A folder of recordings to try the detector on. Nothing is written into it.")
        choose_folder.clicked.connect(self.choose_example_folder)
        choose_roi = QPushButton("ROI file…")
        choose_roi.setToolTip("Take the release centre and the electrode from an ROI file of ROI Selection.")
        choose_roi.clicked.connect(self.choose_roi_file)
        self.recording_box = QComboBox()
        self.recording_box.setMinimumWidth(120)
        self.recording_box.activated.connect(lambda _: self.search())
        self.search_button = QPushButton("Search")
        self.search_button.setToolTip("Search the example recording with the settings shown.")
        self.search_button.clicked.connect(self.search)
        example_row = QHBoxLayout()
        example_row.addWidget(choose_folder)
        self.folder_label = QLabel("No example folder")
        example_row.addWidget(self.folder_label, 1)
        example_row.addWidget(choose_roi)
        example_row.addWidget(QLabel("Recording:"))
        example_row.addWidget(self.recording_box)
        example_row.addWidget(self.search_button)
        self.roi_label = _grey()
        self.status = QLabel()
        self.status.setWordWrap(True)

        self.figure = Figure(layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(300)
        grid_spec = self.figure.add_gridspec(2, 2, height_ratios=[3, 2])
        self.map_axes = self.figure.add_subplot(grid_spec[0, 0])
        self.event_axes = self.figure.add_subplot(grid_spec[0, 1])
        self.trace_axes = self.figure.add_subplot(grid_spec[1, :])
        self.colorbar = None
        self.canvas.mpl_connect("button_press_event", self.clicked_map)

        self.table = QTableWidget(0, 1)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.row_selected)
        self.recording_values = QLabel()
        self.recording_values.setWordWrap(True)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addLayout(example_row)
        right_layout.addWidget(self.roi_label)
        right_layout.addWidget(self.status)
        splitter_right = QSplitter(Qt.Vertical)
        splitter_right.addWidget(self.canvas)
        table_part = QWidget()
        table_layout = QVBoxLayout(table_part)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.recording_values)
        table_layout.addWidget(self.table, 1)
        splitter_right.addWidget(table_part)
        splitter_right.setSizes([480, 220])
        right_layout.addWidget(splitter_right, 1)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 900])
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(main)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1450, screen.width() - 40), min(860, screen.height() - 60))
        self.draw_empty("Choose an example folder above to try the detector on a real recording.")

    # ------------------------------------------------------------------
    # The library
    # ------------------------------------------------------------------

    def fill_library(self):
        self.entries = library.entries(self.user_folder)
        labels = [entry.label for entry in self.entries]
        index = next((i for i, e in enumerate(self.entries) if self.entry and e.path == self.entry.path), None)
        if index is None:
            labels.append(f"{self.detector.name}  (not saved)")
            index = len(labels) - 1
        self.library_box.blockSignals(True)
        self.library_box.clear()
        self.library_box.addItems(labels)
        self.library_box.setCurrentIndex(index)
        self.library_box.blockSignals(False)

    def open_entry(self, index):
        if index >= len(self.entries) or not self.may_leave():
            self.fill_library()
            return
        self.entry = self.entries[index]
        try:
            self.detector = self.entry.load()
        except DetectorError as error:
            QMessageBox.warning(self, "Cannot open the detector", str(error))
            return
        self.saved = self.detector.to_dict()
        self.show_detector()
        self.fill_library()
        if self.example is not None:
            self.fill_recordings()

    def show_detector(self):
        d = self.detector
        self.description.setText(d.description)
        self.skip_words.setText(", ".join(d.skip_words))
        self.form.show_settings(d.settings)
        self.event_list.show_chosen(d.event_measures)
        self.recording_list.show_chosen(d.recording_measures)
        self.slice_list.show_chosen(d.slice_measures)
        self.summary_list.show_chosen(d.slice_event_measures)
        for statistic, box in self.statistic_boxes.items():
            box.blockSignals(True)
            box.setChecked(statistic in d.slice_statistics)
            box.blockSignals(False)
        self.delete_button.setEnabled(self.entry is not None and not self.entry.built_in)
        self.show_state()

    @property
    def unsaved(self):
        return self.detector is not None and self.detector.to_dict() != self.saved

    def show_state(self):
        self.state.setText("<span style='color:#b35c00'>  –  changes not saved</span>" if self.unsaved else "")
        problems = self.detector.problems()
        self.problems.setText("<br>".join(f"<span style='color:#c1121f'>⚠ {p}</span>" for p in problems) if problems else
                              "<span style='color:#1a7f37'>✓ The detector is complete.</span>")

    def may_leave(self):
        """True if there are no unsaved changes, or the user agrees to lose them."""
        if not self.unsaved:
            return True
        answer = QMessageBox.question(self, "Unsaved changes", f"The changes to {self.detector.name} are not saved. "
                                      "Discard them?")
        return answer == QMessageBox.Yes

    def save(self):
        if self.entry is None or self.entry.built_in:
            return self.save_as()
        path = library.save_in_library(self.detector, self.user_folder, replacing=self.entry.path)
        self._saved_as(path)

    def save_as(self):
        name, ok = QInputDialog.getText(self, "Save as", "Name of the detector:", text=f"{self.detector.name} (mine)")
        if not ok or not name.strip():
            return
        if library.is_taken(name, self.user_folder):
            QMessageBox.warning(self, "Save as", f"A detector named {name.strip()} exists already. Choose another name.")
            return
        self.detector.name = name.strip()
        self._saved_as(library.save_in_library(self.detector, self.user_folder))

    def _saved_as(self, path):
        self.saved = self.detector.to_dict()
        self.entries = library.entries(self.user_folder)
        self.entry = next(e for e in self.entries if e.path == path)
        self.fill_library()
        self.show_detector()

    def delete(self):
        if self.entry is None or self.entry.built_in:
            return
        answer = QMessageBox.question(self, "Delete", f"Delete {self.detector.name} from the library?")
        if answer == QMessageBox.Yes:
            self.entry.path.unlink(missing_ok=True)
            self.saved = self.detector.to_dict()
            self.entries = library.entries(self.user_folder)
            self.open_entry(0)

    def import_detector(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import a detector", "", "Detector files (*.json)")
        if not path:
            return
        try:
            detector = Detector.load(path)
        except DetectorError as error:
            QMessageBox.warning(self, "Import", str(error))
            return
        if library.is_taken(detector.name, self.user_folder):
            QMessageBox.warning(self, "Import", f"A detector named {detector.name} is in the library already.")
            return
        self.detector = detector
        self._saved_as(library.save_in_library(detector, self.user_folder))

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export the detector", library.file_name(self.detector.name),
                                              "Detector files (*.json)")
        if path:
            self.detector.save(path)

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def edited(self):
        self.detector.description = self.description.text().strip()
        self.detector.skip_words = [w.strip() for w in self.skip_words.text().split(",") if w.strip()]
        self.show_state()
        if self.example is not None:
            self.fill_recordings(search=False)

    def setting_changed(self, name):
        self.detector.settings = self.form.settings()
        self.show_state()
        if self.detection is None:
            return
        if name in MEASURING and self.searched_with is not None:
            self.searched_with = replace(self.searched_with, **{key: getattr(self.detector.settings, key) for key in MEASURING})
            self.events = measure_events(self.detection, self.searched_with, self.example.center, self.example.electrode)
            self.show_results()
        else:
            self.status.setText("<span style='color:#b35c00'>The settings changed: press Search to see them on the "
                                "example.</span>")

    def measures_changed(self):
        d = self.detector
        d.event_measures = self.event_list.chosen()
        d.recording_measures = self.recording_list.chosen()
        d.slice_measures = self.slice_list.chosen()
        d.slice_event_measures = self.summary_list.chosen()
        d.slice_statistics = [s for s, box in self.statistic_boxes.items() if box.isChecked()]
        self.show_state()
        if self.detection is not None:
            self.fill_table()

    # ------------------------------------------------------------------
    # The example
    # ------------------------------------------------------------------

    def choose_example_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder of recordings", remembered("spontaneous_example_folder"))
        if folder:
            self.use_example_folder(Path(folder), remembered("spontaneous_roi_file") or None)

    def choose_roi_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose an ROI file", remembered("spontaneous_roi_file"),
                                              "ROI files (roi_selections.json);;All files (*.json)")
        if path:
            remember(spontaneous_roi_file=path)
            if self.example is not None:
                self.use_example_folder(self.example.folder, path)

    def use_example_folder(self, folder, roi_file):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.example = ExampleFolder(folder, roi_file)
        except (OSError, ValueError) as error:
            self.example = None
            self.roi_label.setText(f"⚠ {error}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        remember(spontaneous_example_folder=str(folder))
        self.folder_label.setText(str(folder) if len(str(folder)) < 70 else "…" + str(folder)[-68:])
        self.folder_label.setToolTip(str(folder))
        self.roi_label.setText(self.example.source)
        self.fill_recordings()

    def fill_recordings(self, search=True):
        current = self.recording_box.currentText()
        names = [path.name for path in self.detector.searched_files(self.example.paths)]
        self.recording_box.clear()
        self.recording_box.addItems(names)
        if current in names:
            self.recording_box.setCurrentText(current)
        if not names:
            self.detection = None
            self.draw_empty("This folder has no unstimulated recordings (named 'no' and a number) to search.")
            return
        if search:
            self.search()

    def search(self):
        if self.worker is not None:
            self.search_again = True  # searched as soon as the running search ends
            return
        self.search_again = False
        if self.example is None or self.recording_box.currentIndex() < 0:
            return
        if self.detector.settings.problems():
            self.status.setText("⚠ " + " ".join(self.detector.settings.problems()))
            return
        path = self.example.folder / self.recording_box.currentText()
        try:
            stack = self.example.stack(path)
        except (OSError, ValueError) as error:
            self.draw_empty(str(error))
            return
        settings = self.detector.settings
        self.status.setText(f"Searching {path.name}…")
        self.search_button.setEnabled(False)
        self.worker = SearchWorker(stack, self.example.electrode, settings, self.example.center)
        self.worker.finished.connect(lambda: self.searched(settings, path.name))
        self.worker.start()

    def searched(self, settings, name):
        worker, self.worker = self.worker, None
        self.search_button.setEnabled(True)
        if self.search_again:
            self.search()
            return
        if worker.error is not None:
            self.detection = None
            self.draw_empty(f"The search failed: {worker.error}")
            return
        self.detection, self.events, self.searched_with, self.searched_name = worker.detection, worker.events, settings, name
        self.selected = 0
        self.show_results()

    def show_results(self):
        d, s = self.detection, self.searched_with
        flipped = "off" if d.sign_flipped is None else len(d.sign_flipped)
        reversed_ = "off" if d.time_reversed is None else len(d.time_reversed)
        seconds = d.searched_frames * s.frame_ms / 1000
        events = "1 event" if len(d.events) == 1 else f"{len(d.events)} events"
        self.status.setText(f"{self.searched_name}: <b>{events}</b> in {seconds:.1f} s searched; sign-flipped: {flipped}; "
                            f"time-reversed: {reversed_}.")
        self.fill_table()
        self.draw()

    def fill_table(self):
        keys = self.detector.event_measures
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.setColumnCount(1 + len(keys))
        units = {m.key: m.unit for m in EVENT}
        self.table.setHorizontalHeaderLabels(["Event"] + [f"{key} ({units[key]})" for key in keys])
        for n, values in enumerate(self.events or [], start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(n)))
            for column, key in enumerate(keys, start=1):
                self.table.setItem(row, column, QTableWidgetItem(_format(values.get(key))))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        if self.events:
            self.table.selectRow(min(self.selected, len(self.events) - 1))
        self.table.blockSignals(False)
        values = measure_recording(self.detection, self.searched_with)
        units = {m.key: m.unit for m in RECORDING}
        shown = [f"{key} {_format(values[key])}" + ("" if units[key] == "count" else f" {units[key]}")
                 for key in self.detector.recording_measures]
        self.recording_values.setText("<b>This recording:</b> " + ("; ".join(shown) if shown else "no per-recording measure chosen"))

    def row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.selected = rows[0].row()
            self.draw()

    def clicked_map(self, event):
        """Select the event nearest to a click on the z map."""
        if event.inaxes is not self.map_axes or not self.events:
            return
        s = self.searched_with
        distance = [np.hypot(e["x"] / s.pixel_um - event.xdata, e["y"] / s.pixel_um - event.ydata) for e in self.events]
        self.table.selectRow(int(np.argmin(distance)))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_empty(self, message):
        self.status.setText(message)
        for axes in (self.map_axes, self.event_axes, self.trace_axes):
            axes.clear()
            axes.set_axis_off()
        self.table.setRowCount(0)
        self.recording_values.setText("")
        self.canvas.draw_idle()

    def draw(self):
        d, s = self.detection, self.searched_with
        for axes in (self.map_axes, self.event_axes, self.trace_axes):
            axes.clear()
            axes.set_axis_on()
        image = self.map_axes.imshow(np.where(d.tissue, d.peak_z, np.nan), cmap="magma", vmin=0, vmax=max(2 * s.event_z, 1))
        if self.colorbar is None:
            self.colorbar = self.figure.colorbar(image, ax=self.map_axes, label="largest z", shrink=0.9)
        else:
            self.colorbar.update_normal(image)
        if self.example.electrode is not None and self.example.electrode.any():
            self.map_axes.contour(self.example.electrode, [0.5], colors="cyan", linewidths=1)
        self.map_axes.plot(*self.example.center, "+", color="white", markersize=10)
        for n, e in enumerate(self.events, start=1):
            x, y = e["x"] / s.pixel_um, e["y"] / s.pixel_um
            chosen = n - 1 == self.selected
            self.map_axes.add_patch(Circle((x, y), 6, fill=False, color="lime" if chosen else "white", linewidth=1.5 if chosen else 1))
            self.map_axes.annotate(str(n), (x + 6, y - 6), color="lime" if chosen else "white", fontsize=8)
        self.map_axes.set_title("Each pixel's largest z; events circled, + the release centre", fontsize=9)
        self.map_axes.set_xticks([])
        self.map_axes.set_yticks([])
        if not self.events:
            self.event_axes.set_axis_off()
            self.trace_axes.set_axis_off()
            self.event_axes.text(0.5, 0.5, "No event in this recording.", ha="center", va="center", transform=self.event_axes.transAxes)
            self.canvas.draw_idle()
            return
        e = self.events[min(self.selected, len(self.events) - 1)]
        frame, row, col, _ = d.events[min(self.selected, len(self.events) - 1)]
        onset = int(frame) - d.first_frame
        peak = peak_map(d, onset, int(row), int(col), s)
        if peak is not None:
            span = 25
            r0, c0 = max(int(row) - span, 0), max(int(col) - span, 0)
            part = peak[r0 : int(row) + span + 1, c0 : int(col) + span + 1] * 100
            self.event_axes.imshow(part, cmap="viridis", extent=(c0 - 0.5, c0 + part.shape[1] - 0.5, r0 + part.shape[0] - 0.5, r0 - 0.5))
            if np.isfinite(e["width"]):
                half = np.sqrt(2 * np.log(2)) * e["width"] / s.pixel_um
                self.event_axes.add_patch(Circle((e["x"] / s.pixel_um, e["y"] / s.pixel_um), half, fill=False, color="white"))
            self.event_axes.set_title(f"Event {self.selected + 1}: peak map (% dF/F); circle: half maximum", fontsize=9)
            self.event_axes.set_xticks([])
            self.event_axes.set_yticks([])
        trace = event_trace(d, s, onset, int(row), int(col))
        if trace is not None:
            times = (np.arange(len(trace)) - 60) * s.frame_ms
            self.trace_axes.plot(times, (trace - np.median(trace[:50])) * 100, color="tab:blue", linewidth=1)
            self.trace_axes.axvline(0, color="gray", linestyle="--", linewidth=1)
            self.trace_axes.set_xlabel("ms from the onset")
            self.trace_axes.set_ylabel("pooled dF/F (%)")
            self.trace_axes.set_title(f"Event {self.selected + 1}: pooled trace at its maximum (z {e['z']:.1f})", fontsize=9)
        self.canvas.draw_idle()

    def closeEvent(self, event):
        if not self.may_leave():
            event.ignore()
            return
        if self.worker is not None:
            self.worker.wait()
        self.closed.emit()
        super().closeEvent(event)
