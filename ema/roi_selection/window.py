"""The ROI Selection window: go through the recording folders, check and correct each ROI and electrode."""

from functools import lru_cache

import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..recordings import find_recording_folders, is_online_only, list_recordings, load_stack
from .detection import baseline_image, detect_folder, detection_files, response_map, roi_trace
from .plots import EDIT_ELECTRODE, MOVE_ROI, ImageView, TraceView
from .selections import AUTOMATIC, FILE_NAME, MANUAL, FolderSelection
from .setup_dialog import SetupDialog

VIEW_RESPONSE = "Response of this recording"
VIEW_MEAN = "Mean response (used for the automatic ROI)"
VIEW_BASELINE = "Baseline image"
VIEW_MOVIE = "Movie"
HINTS = {
    MOVE_ROI: "Click or drag on the image to move the ROI.",
    EDIT_ELECTRODE: "Drag to outline an area: the left button adds it to the electrode, the right button removes it.",
}
FLAG = "⚑"


class RoiSelectionWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, selections, output_folder):
        super().__init__()
        self.setWindowTitle("EMA – ROI Selection")
        self.selections = selections
        self.output_folder = output_folder
        self.folders = find_recording_folders(selections.recordings_folder)
        self.load = lru_cache(maxsize=4)(load_stack)
        self.detect = lru_cache(maxsize=32)(self._detect)
        self.downloads_allowed = None  # asked once, when an online-only recording is first needed

        # What is open right now
        self.folder = None
        self.recordings = []
        self.detection = None
        self.selection = None
        self.stack = None
        self.baseline = self.response = None

        self._build_window()
        self.fill_folder_list()
        if self.folders:
            self.folder_list.setCurrentRow(0)
        else:
            self.show_problem("No TIFF movies were found in the recordings folder.")

    @property
    def settings(self):
        return self.selections.settings

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def _build_window(self):
        self.folder_list = QListWidget()
        self.folder_list.currentRowChanged.connect(self.open_folder)
        self.progress_label = QLabel()
        detect_all = QPushButton("Detect all folders")
        detect_all.setToolTip("Find the ROI and electrode of every folder that has none yet.")
        detect_all.clicked.connect(self.detect_all)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("<b>Recording folders</b>"))
        side_layout.addWidget(self.folder_list, 1)
        side_layout.addWidget(self.progress_label)
        side_layout.addWidget(detect_all)

        self.recording_box = QComboBox()
        self.recording_box.setMinimumWidth(180)
        self.recording_box.currentIndexChanged.connect(self.open_recording)
        self.view_box = QComboBox()
        self.view_box.addItems([VIEW_RESPONSE, VIEW_MEAN, VIEW_BASELINE, VIEW_MOVIE])
        self.view_box.currentIndexChanged.connect(self.show_image)
        settings_button = QPushButton("Settings…")
        settings_button.clicked.connect(self.change_settings)
        export_button = QPushButton("Export table…")
        export_button.setToolTip("Save one row per folder as a CSV file for Excel.")
        export_button.clicked.connect(self.export_table)

        top = QHBoxLayout()
        top.addWidget(QLabel("Recording:"))
        top.addWidget(self.recording_box)
        top.addSpacing(15)
        top.addWidget(QLabel("Show:"))
        top.addWidget(self.view_box)
        top.addStretch()
        top.addWidget(settings_button)
        top.addWidget(export_button)

        self.image = ImageView()
        self.image.roi_moved.connect(self.move_roi)
        self.image.roi_dropped.connect(self.drop_roi)
        self.image.electrode_outlined.connect(self.edit_electrode)
        self.trace = TraceView()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.show_frame)
        self.frame_label = QLabel()
        self.movie_row = QWidget()
        movie_layout = QHBoxLayout(self.movie_row)
        movie_layout.setContentsMargins(0, 0, 0, 0)
        movie_layout.addWidget(self.slider, 1)
        movie_layout.addWidget(self.frame_label)

        image_side = QVBoxLayout()
        image_side.addWidget(self.image, 1)
        image_side.addWidget(self.movie_row)
        plots = QHBoxLayout()
        plots.addLayout(image_side, 4)
        plots.addWidget(self.trace, 5)

        self.roi_tool = QRadioButton("Move the ROI")
        self.roi_tool.setChecked(True)
        self.roi_tool.toggled.connect(self.choose_tool)
        self.electrode_tool = QRadioButton("Edit the electrode")
        automatic_roi = QPushButton("Automatic ROI")
        automatic_roi.setToolTip("Put the ROI back where it was found automatically.")
        automatic_roi.clicked.connect(self.use_automatic_roi)
        automatic_electrode = QPushButton("Automatic electrode")
        automatic_electrode.setToolTip("Put back the electrode mask that was found automatically.")
        automatic_electrode.clicked.connect(self.use_automatic_electrode)
        no_electrode = QPushButton("No electrode")
        no_electrode.setToolTip("Remove the electrode mask, for example to draw it from scratch.")
        no_electrode.clicked.connect(self.remove_electrode)
        tools = QHBoxLayout()
        tools.addWidget(QLabel("Mouse:"))
        tools.addWidget(self.roi_tool)
        tools.addWidget(self.electrode_tool)
        tools.addSpacing(15)
        tools.addWidget(automatic_roi)
        tools.addWidget(automatic_electrode)
        tools.addWidget(no_electrode)
        tools.addStretch()

        self.flag_box = QCheckBox(f"{FLAG} Flag this recording")
        self.flag_box.setToolTip("Mark a recording that fails your criteria. Later analysis can leave flagged recordings out.")
        self.flag_box.clicked.connect(self.flag_recording)
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Reason (optional), for example: no response")
        self.reason.textEdited.connect(lambda: self.flag_recording(True))
        flag_all = QPushButton("Flag all in this folder")
        flag_all.setToolTip("Flag every recording of this folder, with the reason typed on the left.")
        flag_all.clicked.connect(self.flag_folder)
        flags = QHBoxLayout()
        flags.addWidget(self.flag_box)
        flags.addWidget(self.reason, 1)
        flags.addWidget(flag_all)

        self.hint = QLabel(HINTS[MOVE_ROI])
        self.hint.setStyleSheet("color: gray")
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        previous = QPushButton("← Previous")
        previous.clicked.connect(lambda: self.step(-1))
        self.accept_button = QPushButton("Accept and next →")
        self.accept_button.setToolTip("Mark this folder as reviewed and open the next one (Ctrl+Enter).")
        self.accept_button.setShortcut("Ctrl+Return")
        self.accept_button.setDefault(True)
        self.accept_button.clicked.connect(self.accept_and_next)
        bottom = QHBoxLayout()
        bottom.addWidget(self.hint, 1)
        bottom.addWidget(previous)
        bottom.addWidget(self.accept_button)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.addLayout(top)
        main_layout.addLayout(plots, 1)
        main_layout.addLayout(tools)
        main_layout.addLayout(flags)
        main_layout.addLayout(bottom)
        # Everything that only makes sense while a folder is open
        self.editing_widgets = [
            self.recording_box, self.view_box, self.image, self.roi_tool, self.electrode_tool, automatic_roi,
            automatic_electrode, no_electrode, self.flag_box, self.reason, flag_all, self.accept_button,
        ]

        splitter = QSplitter()
        splitter.addWidget(side)
        splitter.addWidget(main)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 1000])
        self.setCentralWidget(splitter)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1320, screen.width() - 40), min(760, screen.height() - 60))

    # ------------------------------------------------------------------
    # The folder list
    # ------------------------------------------------------------------

    def fill_folder_list(self):
        self.folder_list.blockSignals(True)
        row = self.folder_list.currentRow()
        self.folder_list.clear()
        self.folder_list.addItems([""] * len(self.folders))
        for index in range(len(self.folders)):
            self.show_folder_state(index)
        self.folder_list.setCurrentRow(row)
        self.folder_list.blockSignals(False)

    def show_folder_state(self, row=None):
        """Update one line of the folder list (the open folder by default) and the progress count."""
        if row is None:
            row = self.folder_list.currentRow()
        folder = self.folders[row]
        selection = self.selections.of(folder)
        name = self.selections.name_of(folder)
        name = folder.name if name == "." else name
        marks, tips, color = "", [], QColor("black")
        if selection is None:
            tips.append("Not detected yet.")
            color = QColor("gray")
        else:
            if selection.reviewed:
                marks += "✓ "
                tips.append("Reviewed.")
                color = QColor("#1a7f37")
            if selection.flagged_files:
                marks += FLAG + " "
                tips.append(f"{len(selection.flagged_files)} flagged recording(s).")
            if selection.peak_response_percent < self.settings.low_response_percent:
                marks += "⚠ "
                tips.append(f"Low response: {selection.peak_response_percent:.1f} % at the automatic ROI.")
        item = self.folder_list.item(row)
        item.setText(marks + name)
        item.setToolTip(" ".join(tips))
        item.setForeground(color)
        reviewed = sum(s.reviewed for s in self.selections.folders.values())
        self.progress_label.setText(f"{reviewed} of {len(self.folders)} folders reviewed")

    # ------------------------------------------------------------------
    # Opening a folder and a recording
    # ------------------------------------------------------------------

    def _detect(self, folder):
        return detect_folder(folder, self.settings, load=self.load)

    def may_read(self, paths):
        """False if reading these files would download them from OneDrive and the user does not want that."""
        if not any(is_online_only(path) for path in paths):
            return True
        if self.downloads_allowed is None:
            answer = QMessageBox.question(
                self,
                "Online-only recordings",
                "Some recordings are stored online only (OneDrive). Reading them downloads them to this "
                "computer.\n\nDownload recordings when they are needed?",
            )
            self.downloads_allowed = answer == QMessageBox.Yes
        return self.downloads_allowed

    def open_folder(self, row):
        if row < 0:
            return
        self.folder = self.folders[row]
        self.recordings = list_recordings(self.folder)
        self.detection = self.selection = self.stack = None
        used = detection_files(self.recordings, self.settings)
        if not self.may_read(used):
            return self.show_problem("These recordings are online only and were not downloaded.")

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.detection = self.detect(self.folder)
        except (OSError, ValueError) as error:
            return self.show_problem(str(error))
        finally:
            QApplication.restoreOverrideCursor()

        self.selection = self.selections.of(self.folder)
        if self.selection is None:
            self.selection = FolderSelection.from_detection(self.detection, self.settings)
            self.selections.folders[self.selections.name_of(self.folder)] = self.selection
            self.save()

        for widget in self.editing_widgets:
            widget.setEnabled(True)
        self.recording_box.blockSignals(True)
        self.recording_box.clear()
        self.recording_box.addItems([path.name for path in self.recordings])
        self.recording_box.blockSignals(False)
        self.show_flag_marks()
        first = self.recordings.index(used[0])
        self.recording_box.setCurrentIndex(first)
        self.open_recording(first)

    def open_recording(self, index):
        if index < 0 or self.selection is None:
            return
        path = self.recordings[index]
        self.stack = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if not self.may_read([path]):
                raise ValueError(f"{path.name} is online only and was not downloaded.")
            stack = self.load(path)
            if stack.shape[1:] != self.selection.image_shape:
                raise ValueError(f"{path.name} has another image size than the rest of the folder.")
            self.baseline = baseline_image(stack, self.settings)
            self.response = response_map(stack, self.settings)
            self.stack = stack
        except (OSError, ValueError) as error:
            self.trace.clear()
            self.status.setText(f"⚠ {error}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.movie_limits = tuple(np.percentile(stack[::50], [1, 99.9]))
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(stack) - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.show_flag()
        self.show_image()
        self.image.show_roi(self.selection.roi_center, self.selection.roi_radius_px)
        self.image.show_electrode(self.selection.electrode_mask)
        self.trace.show_trace(self.roi_trace(), self.settings, title=path.name)
        self.show_frame(self.slider.value())
        self.show_status()

    def show_problem(self, message):
        """Empty the plots and say why this folder cannot be shown."""
        for widget in self.editing_widgets:
            widget.setEnabled(False)
        self.recording_box.clear()
        self.trace.clear()
        self.status.setText(f"⚠ {message}")

    # ------------------------------------------------------------------
    # Image and trace
    # ------------------------------------------------------------------

    def show_image(self):
        if self.stack is None:
            return
        view = self.view_box.currentText()
        self.movie_row.setVisible(view == VIEW_MOVIE)
        if view == VIEW_MOVIE:
            self.show_frame(self.slider.value())
        elif view == VIEW_BASELINE:
            self.image.show_image(self.baseline, "Baseline brightness, F0 (counts)", "gray")
        elif view == VIEW_RESPONSE:
            self.image.show_image(self.response * 100, "Response at the peak, dF/F (%)")
        else:
            files = ", ".join(self.detection.files)
            self.image.show_image(self.detection.response * 100, f"Mean response of {files}, dF/F (%)")
        if view != VIEW_MOVIE:
            self.trace.show_frame(None)

    def show_frame(self, frame):
        if self.stack is None or self.view_box.currentText() != VIEW_MOVIE:
            return
        self.image.show_image(self.stack[frame], "Brightness (counts)", "gray", self.movie_limits)
        self.trace.show_frame(frame)
        self.frame_label.setText(f"Frame {frame} of {len(self.stack) - 1}")

    def roi_trace(self):
        return roi_trace(self.stack, self.selection.roi_center, self.selection.roi_radius_px, self.settings)

    def show_status(self):
        s, um = self.selection, self.settings.pixel_size_um
        self.status.setText(
            f"ROI: {s.roi_source}, centre ({s.roi_center[0]}, {s.roi_center[1]}), "
            f"radius {s.roi_radius_px} px ({s.roi_radius_px * um:.0f} µm)      "
            f"Electrode: {s.electrode_source}, {int(s.electrode_mask.sum())} px      "
            f"Response at the automatic ROI: {s.peak_response_percent:.1f} %"
        )

    # ------------------------------------------------------------------
    # Changing the ROI and the electrode
    # ------------------------------------------------------------------

    def choose_tool(self):
        self.image.tool = MOVE_ROI if self.roi_tool.isChecked() else EDIT_ELECTRODE
        self.hint.setText(HINTS[self.image.tool])

    def move_roi(self, x, y):
        self.selection.roi_center = (x, y)
        self.selection.roi_source = MANUAL
        self.image.show_roi(self.selection.roi_center, self.selection.roi_radius_px)
        if self.stack is not None:
            self.trace.update_trace(self.roi_trace())
        self.show_status()

    def drop_roi(self):
        """The ROI has stopped moving: rescale the trace plot and save."""
        if self.stack is not None:
            name = self.recordings[self.recording_box.currentIndex()].name
            self.trace.show_trace(self.roi_trace(), self.settings, title=name)
            self.show_frame(self.slider.value())
        self.show_status()
        self.save()

    def use_automatic_roi(self):
        self.move_roi(*self.detection.center)
        self.selection.roi_source = AUTOMATIC
        self.drop_roi()

    def edit_electrode(self, area, add):
        mask = self.selection.electrode_mask
        self.set_electrode(mask | area if add else mask & ~area, MANUAL)

    def use_automatic_electrode(self):
        self.set_electrode(self.detection.electrode.copy(), AUTOMATIC)

    def remove_electrode(self):
        self.set_electrode(np.zeros(self.selection.image_shape, bool), MANUAL)

    def set_electrode(self, mask, source):
        self.selection.electrode_mask = mask
        self.selection.electrode_source = source
        self.image.show_electrode(mask)
        self.show_status()
        self.save()

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    def flag_recording(self, flagged):
        name = self.recordings[self.recording_box.currentIndex()].name
        if flagged:
            self.selection.flagged_files[name] = self.reason.text().strip()
        else:
            self.selection.flagged_files.pop(name, None)
        self.flag_box.setChecked(flagged)
        self.show_flag_marks()
        self.save()

    def flag_folder(self):
        for path in self.recordings:
            self.selection.flagged_files[path.name] = self.reason.text().strip()
        self.show_flag()
        self.show_flag_marks()
        self.save()

    def show_flag(self):
        """Show whether the open recording is flagged, and why."""
        name = self.recordings[self.recording_box.currentIndex()].name
        self.flag_box.setChecked(self.selection.is_flagged(name))
        self.reason.setText(self.selection.flagged_files.get(name, ""))

    def show_flag_marks(self):
        """Put a flag in front of every flagged recording in the drop-down list."""
        for index, path in enumerate(self.recordings):
            mark = FLAG + " " if self.selection.is_flagged(path.name) else ""
            self.recording_box.setItemText(index, mark + path.name)

    # ------------------------------------------------------------------
    # Moving on, saving, settings
    # ------------------------------------------------------------------

    def accept_and_next(self):
        self.selection.reviewed = True
        self.save()
        if self.folder_list.currentRow() == len(self.folders) - 1:
            self.status.setText("✓ That was the last folder. Everything is saved in " + str(self.output_folder / FILE_NAME))
        self.step(+1)

    def step(self, direction):
        row = self.folder_list.currentRow() + direction
        if 0 <= row < len(self.folders):
            self.folder_list.setCurrentRow(row)

    def save(self):
        if self.selection is not None:
            self.show_folder_state()
        try:
            self.selections.save(self.output_folder / FILE_NAME)
        except OSError as error:
            QMessageBox.warning(self, "Could not save", f"The selections could not be saved:\n{error}")

    def detect_all(self):
        """Detect every folder that has no selection yet, with a progress bar that can be cancelled."""
        todo = [folder for folder in self.folders if self.selections.of(folder) is None]
        progress = QProgressDialog("Finding ROIs and electrodes…", "Stop", 0, len(todo), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        skipped = 0
        for count, folder in enumerate(todo):
            progress.setValue(count)
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            try:
                if not self.may_read(detection_files(list_recordings(folder), self.settings)):
                    raise ValueError("online only")
                detection = self._detect(folder)
            except (OSError, ValueError):
                skipped += 1
                continue
            name = self.selections.name_of(folder)
            self.selections.folders[name] = FolderSelection.from_detection(detection, self.settings)
            self.show_folder_state(self.folders.index(folder))
        progress.setValue(len(todo))
        self.save()
        if skipped:
            QMessageBox.information(
                self, "Detect all folders", f"{skipped} folder(s) could not be detected. Open them to see why."
            )
        if self.selection is None and self.folder_list.currentRow() >= 0:
            self.open_folder(self.folder_list.currentRow())

    def change_settings(self):
        before = self.settings
        dialog = SetupDialog(self, self.selections, self.output_folder)
        if dialog.exec_() and self.settings != before:
            self.detect.cache_clear()
            self.selection = None
            self.save()
            self.fill_folder_list()
            self.open_folder(self.folder_list.currentRow())

    def export_table(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export table", str(self.output_folder / "roi_selections.csv"), "CSV table (*.csv)"
        )
        if not path:
            return
        try:
            self.selections.export_table(path)
        except OSError as error:
            QMessageBox.warning(self, "Could not export", f"{error}\n\nIf the file is open in Excel, close it and try again.")

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
