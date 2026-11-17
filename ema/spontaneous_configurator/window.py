"""The Spontaneous Event Configurator: make, check and save detectors, tried on an example recording."""

import traceback
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
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..spontaneous.catalogue import EVENT, RECORDING, SLICE, STATISTICS
from ..spontaneous.detection import detect
from ..spontaneous.measures import BASELINE_END, TRACE_BEFORE, event_trace, measure_events, measure_recording, peak_map
from ..spontaneous.presets import LIBRARY
from ..spontaneous.settings import GROUPS, DetectorSettings
from ..user_settings import remember, remembered
from ..widgets import ERROR_COLOUR, OK_COLOUR, WARNING_COLOUR, Checklist, LibraryBar, SettingsForm, coloured, hint, scrolled
from ..widgets import with_unit
from .example import ExampleFolder

MEASURING = {f.name for f in fields(DetectorSettings) if f.metadata["group"] == "Measuring"}


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
        self.details = ""

    def run(self):
        stack, electrode, settings, center = self.args
        try:
            self.detection = detect(stack, electrode, settings)
            self.events = measure_events(self.detection, settings, center, electrode)
        except Exception as error:  # noqa: BLE001  shown in the window, instead of being lost in the thread
            self.error, self.details = error, traceback.format_exc()


class SpontaneousConfiguratorWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, user_folder=None):
        super().__init__()
        self.setWindowTitle("EMA – Spontaneous Event Configurator")
        self.example = None
        self.detection = self.events = None
        self.searched_with = None  # the settings the example was searched with
        self.worker = None
        self.search_again = False
        self.searched_name = ""
        self.selected = 0
        self.bar = LibraryBar(LIBRARY.in_folder(user_folder))
        self.bar.shown.connect(self.show_detector)
        self._build_window()
        self.bar.open(0)
        folder = remembered("spontaneous_example_folder")
        if folder and Path(folder).is_dir():
            self.use_example_folder(Path(folder), remembered("spontaneous_roi_file") or None)

    @property
    def detector(self):
        return self.bar.item

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def _build_window(self):
        self.description = QLineEdit()
        self.description.setPlaceholderText("What this detector is for")
        self.description.editingFinished.connect(self.edited)
        self.skip_words = QLineEdit()
        self.skip_words.setToolTip("Unstimulated recordings (named 'no' and a number) with one of these words in their name "
                                   "are not searched, for example 'no1 red.tif'. Words separated by commas.")
        self.skip_words.editingFinished.connect(self.edited)
        self.form = SettingsForm(DetectorSettings, GROUPS)
        self.form.changed.connect(self.setting_changed)
        defaults = QPushButton("Restore the defaults")
        defaults.setToolTip("Every setting back to the standard detector's value.")
        defaults.clicked.connect(lambda: (self.form.show_settings(DetectorSettings()), self.setting_changed("")))
        detector_page = QWidget()
        page = QVBoxLayout(detector_page)
        about = QFormLayout()
        about.addRow("Description:", self.description)
        about.addRow("Skip recordings with these words:", self.skip_words)
        page.addLayout(about)
        page.addWidget(hint("Strength is how many times the noise level a signal rises, after the detector's filters; an "
                            "event must reach the event threshold. Click a heading to see its settings, and hover over a "
                            "setting for what it does. The defaults are the standard detector's."))
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
        self.tabs.addTab(scrolled(detector_page), "1  Detector")
        self.tabs.addTab(scrolled(self.event_list), "2  Per event")
        self.tabs.addTab(scrolled(slice_page), "3  Per recording and slice")
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
        choose_roi.setToolTip("Take the ROI centre and the electrode from an ROI file of ROI Selection.")
        choose_roi.clicked.connect(self.choose_roi_file)
        self.recording_box = QComboBox()
        self.recording_box.setMinimumWidth(120)
        self.recording_box.activated.connect(lambda _: self.search())
        self.search_button = QPushButton("Search")
        self.search_button.setToolTip("Search the example recording with the settings shown.")
        self.search_button.clicked.connect(self.search)
        self.search_button.setEnabled(False)
        example_row = QHBoxLayout()
        example_row.addWidget(choose_folder)
        self.folder_label = QLabel("No example folder")
        example_row.addWidget(self.folder_label, 1)
        example_row.addWidget(choose_roi)
        example_row.addWidget(QLabel("Recording:"))
        example_row.addWidget(self.recording_box)
        example_row.addWidget(self.search_button)
        self.roi_label = hint()
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
        self.table.setHorizontalHeaderLabels(["Event"])
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
        layout.addWidget(self.bar)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(main)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1450, screen.width() - 40), min(860, screen.height() - 60))
        self.draw_empty("Choose an example folder above to try the detector on a real recording.")

    # ------------------------------------------------------------------
    # The detector on show
    # ------------------------------------------------------------------

    def show_detector(self):
        d = self.detector
        self.description.setText(d.description)
        self.description.setCursorPosition(0)
        self.description.setToolTip(d.description)
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
        self.show_state()
        if self.example is not None:
            self.fill_recordings()

    def show_state(self):
        self.bar.changed()
        problems = self.detector.problems()
        self.problems.setText("<br>".join(coloured(f"⚠ {p}", ERROR_COLOUR) for p in problems) if problems else
                              coloured("✓ The detector is complete.", OK_COLOUR))

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
            self.status.setText(coloured("The settings changed: press Search to see them on the example.", WARNING_COLOUR))

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
        self.search_button.setEnabled(bool(names))
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
        self.status.setText(f"Searching {path.name}… (a few seconds)")
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
            self.draw_empty(coloured(f"⚠ The search failed: {type(worker.error).__name__}: {worker.error}", ERROR_COLOUR))
            self.status.setToolTip(worker.details)
            return
        self.status.setToolTip("")
        self.detection, self.events, self.searched_with, self.searched_name = worker.detection, worker.events, settings, name
        self.selected = 0
        self.show_results()

    def show_results(self):
        d, s = self.detection, self.searched_with
        seconds = d.searched_frames * s.frame_ms / 1000
        events = "1 event" if len(d.events) == 1 else f"{len(d.events)} events"
        checks = []
        if d.sign_flipped is not None:
            checks.append(f"{len(d.sign_flipped)} found upside down")
        if d.time_reversed is not None:
            checks.append(f"{len(d.time_reversed)} found played backwards")
        text = f"{self.searched_name}: <b>{events}</b> in {seconds:.1f} s searched."
        if checks:
            text += " False-alarm checks: " + ", ".join(checks) + "."
        self.status.setText(text)
        self.fill_table()
        self.draw()

    def fill_table(self):
        measures = self.detector.event_columns()
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.setColumnCount(1 + len(measures))
        self.table.setHorizontalHeaderLabels(["Event"] + [with_unit(m.key, m.unit) for m in measures])
        for n, values in enumerate(self.events or [], start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(n)))
            for column, m in enumerate(measures, start=1):
                self.table.setItem(row, column, QTableWidgetItem(_format(values.get(m.key))))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        if self.events:
            self.table.selectRow(min(self.selected, len(self.events) - 1))
        self.table.blockSignals(False)
        values = measure_recording(self.detection, self.searched_with)
        shown = [f"{m.key} {_format(values[m.key])}" + (f" {m.unit}" if m.unit else "")
                 for m in self.detector.recording_columns()]
        self.recording_values.setText("<b>This recording:</b> " + ("; ".join(shown) if shown else "no per-recording measure chosen"))

    def row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.selected = rows[0].row()
            self.draw()

    def clicked_map(self, event):
        """Select the event nearest to a click on the map."""
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
            self.colorbar = self.figure.colorbar(image, ax=self.map_axes, label="strength (× noise)", shrink=0.9)
        else:
            self.colorbar.update_normal(image)
        if self.example.electrode is not None and self.example.electrode.any():
            self.map_axes.contour(self.example.electrode, [0.5], colors="cyan", linewidths=1)
        if self.example.center is not None:
            self.map_axes.plot(*self.example.center, "+", color="white", markersize=10)
        for n, e in enumerate(self.events, start=1):
            x, y = e["x"] / s.pixel_um, e["y"] / s.pixel_um
            chosen = n - 1 == self.selected
            self.map_axes.add_patch(Circle((x, y), 6, fill=False, color="lime" if chosen else "white", linewidth=1.5 if chosen else 1))
            self.map_axes.annotate(str(n), (x + 6, y - 6), color="lime" if chosen else "white", fontsize=8)
        self.map_axes.set_title("Strongest signal; events circled,\n+ the ROI centre, electrode in cyan", fontsize=9)
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
            times = (np.arange(len(trace)) - TRACE_BEFORE) * s.frame_ms
            self.trace_axes.plot(times, (trace - np.median(trace[: TRACE_BEFORE + BASELINE_END])) * 100, color="tab:blue",
                                 linewidth=1)
            self.trace_axes.axvline(0, color="gray", linestyle="--", linewidth=1)
            self.trace_axes.set_xlabel("ms from the onset")
            self.trace_axes.set_ylabel("dF/F around the event (%)")
            self.trace_axes.set_title(f"Event {self.selected + 1}: its trace, pooled over the filter width "
                                      f"(strength {e['strength']:.1f} × noise)", fontsize=9)
        self.canvas.draw_idle()

    def closeEvent(self, event):  # noqa: N802 (Qt's name)
        if not self.bar.may_leave():
            event.ignore()
            return
        if self.worker is not None:
            self.worker.wait()
        self.closed.emit()
        super().closeEvent(event)
