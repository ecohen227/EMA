"""The ROI Selection window: go through the recording folders, check and correct each ROI and electrode."""

from functools import lru_cache

import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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

from ..recordings import list_recordings, load_stack
from .detection import baseline_image, detect, folder_mean, peak_frame, response_at, roi_trace
from .plots import EDIT_ELECTRODE, MOVE_ROI, ImageView, TraceView
from .selections import AUTOMATIC, FILE_NAME, MANUAL, FolderSelection
from .setup_dialog import SetupDialog
from .strip import FLAG, RecordingStrip

MEAN = "mean"  # stands for the mean recording wherever a recording's file name is expected
VIEW_RESPONSE = "Response (dF/F)"
VIEW_MOVIE = "Brightness"
VIEW_BASELINE = "Baseline image"
STRIP_HINT = "Strip: click a recording to show it, right-click to flag it."
HINTS = {
    MOVE_ROI: "Image: click or drag to move the ROI.    " + STRIP_HINT,
    EDIT_ELECTRODE: "Image: outline an area; the left button adds it to the electrode, the right button removes it.",
}


class RoiSelectionWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, selections, output_folder):
        super().__init__()
        self.setWindowTitle("EMA – ROI Selection")
        self.selections = selections
        self.output_folder = output_folder
        self.folders = selections.recording_folders()

        # Recordings are large and slow to read, so the last ones stay in memory.
        self.load = lru_cache(maxsize=24)(load_stack)
        self.folder_mean = lru_cache(maxsize=2)(self._folder_mean)
        self.detect = lru_cache(maxsize=32)(self._detect)

        # What is open right now
        self.folder = None
        self.recordings = []  # paths of the recordings of the open folder
        self.detection = None
        self.selection = None
        self.stack = None  # the movie on show: one recording, or the mean recording
        self.baseline = None
        self.cards_to_fill = []
        self.strip_timer = QTimer(self)
        self.strip_timer.setSingleShot(True)
        self.strip_timer.timeout.connect(self.fill_next_card)

        self._build_window()
        self.fill_folder_list()
        if self.folders:
            self.folder_list.setCurrentRow(0)
        else:
            self.show_problem("No recording folders. Check the recordings folder and the folder filter under Settings…")

    @property
    def settings(self):
        return self.selections.settings

    @property
    def recording(self):
        """The file name of the recording on show, or MEAN."""
        return self.recording_box.currentData()

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def _build_window(self):
        self.folder_list = QListWidget()
        self.folder_list.currentRowChanged.connect(self.open_folder)
        self.progress_label = QLabel()
        detect_all = QPushButton("Detect all folders")
        detect_all.setToolTip("Find the ROI and electrode of every folder that was not detected with these settings yet.")
        detect_all.clicked.connect(self.detect_all)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("<b>Recording folders</b>"))
        side_layout.addWidget(self.folder_list, 1)
        side_layout.addWidget(self.progress_label)
        side_layout.addWidget(detect_all)

        self.recording_box = QComboBox()
        self.recording_box.setMinimumWidth(200)
        self.recording_box.currentIndexChanged.connect(self.open_recording)
        self.view_box = QComboBox()
        self.view_box.addItems([VIEW_RESPONSE, VIEW_MOVIE, VIEW_BASELINE])
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
        self.slider.setToolTip("The frame on show. It starts at the peak of the response.")
        self.slider.valueChanged.connect(self.show_image)
        self.frame_label = QLabel()
        slider_row = QHBoxLayout()
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(self.frame_label)

        image_side = QVBoxLayout()
        image_side.addWidget(self.image, 1)
        image_side.addLayout(slider_row)
        plots = QHBoxLayout()
        plots.addLayout(image_side, 4)
        plots.addWidget(self.trace, 5)

        self.strip = RecordingStrip()
        self.strip.selected.connect(self.choose_recording)
        self.strip.flag_toggled.connect(self.toggle_flag)

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

        self.flag_box = QCheckBox(f"{FLAG} Flag this recording")
        self.flag_box.setToolTip("Mark a recording that fails your criteria. Later analysis can leave flagged recordings out.")
        self.flag_box.clicked.connect(self.flag_recording)
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Reason (optional), for example: no response")
        self.reason.textEdited.connect(lambda: self.flag_recording(True))
        flag_all = QPushButton("Flag all in this folder…")
        flag_all.setToolTip("Flag every recording of this folder.")
        flag_all.clicked.connect(self.flag_folder)

        tools = QHBoxLayout()
        tools.addWidget(QLabel("Mouse:"))
        tools.addWidget(self.roi_tool)
        tools.addWidget(self.electrode_tool)
        tools.addWidget(automatic_roi)
        tools.addWidget(automatic_electrode)
        tools.addWidget(no_electrode)
        tools.addStretch()
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
        main_layout.addWidget(self.strip)
        main_layout.addLayout(tools)
        main_layout.addLayout(flags)
        main_layout.addLayout(bottom)
        # Everything that only makes sense while a folder is open
        self.editing_widgets = [
            self.recording_box, self.view_box, self.image, self.slider, self.strip, self.roi_tool,
            self.electrode_tool, automatic_roi, automatic_electrode, no_electrode, self.flag_box, self.reason,
            flag_all, self.accept_button,
        ]

        splitter = QSplitter()
        splitter.addWidget(side)
        splitter.addWidget(main)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1100])
        self.setCentralWidget(splitter)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, screen.width() - 40), min(820, screen.height() - 60))

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
        if selection is None or selection.needs_detection:
            tips.append("Not detected yet with these settings.")
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
    # Reading recordings
    # ------------------------------------------------------------------

    def _folder_mean(self, folder):
        return folder_mean(folder, self.settings, self.load)

    def _detect(self, folder):
        stack, files = self.folder_mean(folder)
        return detect(stack, self.settings, files)

    def stack_of(self, recording):
        """The movie of a recording of the open folder (by file name), or of its mean recording."""
        if recording == MEAN:
            return self.folder_mean(self.folder)[0]
        stack = self.load(self.folder / recording)
        if stack.shape[1:] != self.selection.image_shape:
            raise ValueError(f"{recording} has another image size than the rest of the folder.")
        return stack

    # ------------------------------------------------------------------
    # Opening a folder and a recording
    # ------------------------------------------------------------------

    def open_folder(self, row):
        if row < 0:
            return
        self.folder = self.folders[row]
        self.recordings = list_recordings(self.folder)
        self.detection = self.selection = self.stack = None

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
        elif self.selection.needs_detection:  # after a settings change; what was set by hand stays
            self.selection.use_detection(self.detection)
            self.save()

        for widget in self.editing_widgets:
            widget.setEnabled(True)
        used = ", ".join(name.rsplit(".", 1)[0] for name in self.detection.files)
        self.recording_box.blockSignals(True)
        self.recording_box.clear()
        self.recording_box.addItem(f"Mean of {used}", MEAN)
        self.recording_box.insertSeparator(1)
        for path in self.recordings:
            self.recording_box.addItem(path.name, path.name)
        self.recording_box.blockSignals(False)

        self.strip.show_cards({MEAN: "Mean", **{path.name: path.stem for path in self.recordings}}, apart=MEAN)
        self.strip.cards[MEAN].setToolTip(f"The mean of {used}. The automatic ROI and electrode are found on it.")
        self.strip.show_roi(self.selection.roi_center, self.selection.roi_radius_px)
        self.show_flag_marks()
        self.open_recording()
        self.refresh_strip()

    def open_recording(self):
        """Show the recording chosen in the drop-down list."""
        if self.selection is None or self.recording is None:
            return
        self.stack = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            stack = self.stack_of(self.recording)
            self.baseline = baseline_image(stack, self.settings)
            self.peak = peak_frame(stack, self.settings)
            at_peak = response_at(stack, self.peak, self.settings) * 100
            self.stack = stack
        except (OSError, ValueError) as error:
            self.trace.clear()
            self.status.setText(f"⚠ {error}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        # Fixed brightness scales, so the image does not flicker while the slider moves.
        self.response_limits = tuple(np.percentile(at_peak, [1, 99.9]))
        self.movie_limits = tuple(np.percentile(stack[::50], [1, 99.9]))
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(stack) - 1)
        self.slider.setValue(self.peak)
        self.slider.blockSignals(False)

        self.strip.select(self.recording)
        self.show_flag()
        self.show_trace()
        self.image.show_roi(self.selection.roi_center, self.selection.roi_radius_px)
        self.image.show_electrode(self.selection.electrode_mask)
        self.show_status()

    def choose_recording(self, recording):
        self.recording_box.setCurrentIndex(self.recording_box.findData(recording))

    def show_problem(self, message):
        """Empty the plots and say why this folder cannot be shown."""
        for widget in self.editing_widgets:
            widget.setEnabled(False)
        self.cards_to_fill = []
        self.recording_box.clear()
        self.strip.show_cards({})
        self.trace.clear()
        self.status.setText(f"⚠ {message}")

    # ------------------------------------------------------------------
    # Image and trace
    # ------------------------------------------------------------------

    def show_image(self):
        """Draw the image for the chosen view and frame."""
        if self.stack is None:
            return
        view, frame = self.view_box.currentText(), self.slider.value()
        self.slider.setEnabled(view != VIEW_BASELINE)
        if view == VIEW_BASELINE:
            first, last = self.settings.baseline_frames
            self.image.show_image(self.baseline, "Baseline brightness, F0 (counts)", "gray")
            self.frame_label.setText(f"Mean of frames {first} to {last - 1}")
            self.trace.show_frame(None)
            return
        if view == VIEW_RESPONSE:
            response = response_at(self.stack, frame, self.settings) * 100
            self.image.show_image(response, "Response, dF/F (%)", limits=self.response_limits)
        else:
            self.image.show_image(self.stack[frame], "Brightness (counts)", "gray", self.movie_limits)
        at_peak = "  (the peak)" if frame == self.peak else ""
        self.frame_label.setText(f"Frame {frame} of {len(self.stack) - 1}{at_peak}")
        self.trace.show_frame(frame)

    def show_trace(self):
        """Draw the trace of the ROI, and the image with it so that both show the same frame."""
        self.trace.show_trace(self.roi_trace(), self.settings, self.recording_box.currentText(), self.peak)
        self.show_image()

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
    # The strip of all recordings
    # ------------------------------------------------------------------

    def refresh_strip(self):
        """Fill every card of the strip again, one at a time so the window stays usable while recordings load."""
        self.cards_to_fill = [MEAN] + [path.name for path in self.recordings]
        self.strip_timer.start()

    def fill_next_card(self):
        if not self.cards_to_fill or self.selection is None:
            return
        recording = self.cards_to_fill.pop(0)
        try:
            stack = self.stack_of(recording)
            peak = peak_frame(stack, self.settings)
            response = response_at(stack, peak, self.settings) * 100
            trace = roi_trace(stack, self.selection.roi_center, self.selection.roi_radius_px, self.settings)
            start, stop = self.settings.search_frames
            self.strip.fill(recording, response, trace, f"{trace[start:stop].max():.0f} %")
        except (OSError, ValueError) as error:
            self.strip.fail(recording, "cannot be shown", str(error))
        if self.cards_to_fill:
            self.strip_timer.start()

    def finish_strip(self):
        """Fill all remaining cards now, without waiting."""
        while self.cards_to_fill:
            self.fill_next_card()

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
        self.strip.show_roi(self.selection.roi_center, self.selection.roi_radius_px)
        if self.stack is not None:
            self.trace.update_trace(self.roi_trace())
        self.show_status()

    def drop_roi(self):
        """The ROI has stopped moving: rescale the trace plot, renew the strip and save."""
        if self.stack is not None:
            self.show_trace()
        self.refresh_strip()
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
        """Flag or unflag the recording on show, with the reason typed in the box."""
        if flagged:
            self.selection.flagged_files[self.recording] = self.reason.text().strip()
        else:
            self.selection.flagged_files.pop(self.recording, None)
        self.flag_box.setChecked(flagged)
        self.show_flag_marks()
        self.save()

    def toggle_flag(self, recording):
        """A right click on a card: show that recording and flag it, or remove its flag."""
        if recording == MEAN:
            return
        self.choose_recording(recording)
        self.flag_recording(not self.selection.is_flagged(recording))
        if self.selection.is_flagged(recording):
            self.reason.setFocus()  # ready for typing a reason

    def flag_folder(self):
        reason, confirmed = QInputDialog.getText(self, "Flag all in this folder", "Reason (optional):")
        if not confirmed:
            return
        for path in self.recordings:
            self.selection.flagged_files[path.name] = reason.strip()
        self.show_flag()
        self.show_flag_marks()
        self.save()

    def show_flag(self):
        """Show whether the recording on show is flagged, and why. The mean recording cannot be flagged."""
        is_recording = self.recording != MEAN
        self.flag_box.setEnabled(is_recording)
        self.reason.setEnabled(is_recording)
        self.flag_box.setChecked(self.selection.is_flagged(self.recording))
        self.reason.setText(self.selection.flagged_files.get(self.recording, ""))

    def show_flag_marks(self):
        """Mark the flagged recordings in the drop-down list and on the strip."""
        for path in self.recordings:
            mark = FLAG + " " if self.selection.is_flagged(path.name) else ""
            self.recording_box.setItemText(self.recording_box.findData(path.name), mark + path.name)
        self.strip.show_flags(self.selection.flagged_files)

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
        """Detect every folder that has not been detected with these settings, with a progress bar."""
        todo = [f for f in self.folders if self.selections.of(f) is None or self.selections.of(f).needs_detection]
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
                detection = self._detect(folder)
            except (OSError, ValueError):
                skipped += 1
                continue
            selection = self.selections.of(folder)
            if selection is None:
                name = self.selections.name_of(folder)
                self.selections.folders[name] = FolderSelection.from_detection(detection, self.settings)
            else:
                selection.use_detection(detection)
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
        """Open the setup dialog. Afterwards the folder list and the open folder follow what was changed."""
        before = self.settings
        dialog = SetupDialog(self, self.selections, self.output_folder, example_folder=self.folder)
        if not dialog.exec_():
            return
        if self.settings != before:
            self.detect.cache_clear()
            self.folder_mean.cache_clear()
        self.selection = None
        self.save()
        self.folders = self.selections.recording_folders()  # the folder filter may have changed
        row = self.folders.index(self.folder) if self.folder in self.folders else 0
        self.fill_folder_list()
        self.folder_list.blockSignals(True)
        self.folder_list.setCurrentRow(row)
        self.folder_list.blockSignals(False)
        if self.folders:
            self.open_folder(row)
        else:
            self.show_problem("No recording folders pass the folder filter. Change it under Settings…")

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
