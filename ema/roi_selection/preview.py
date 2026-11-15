"""A live example for the setup dialog: what the settings give on one recording folder."""

from functools import lru_cache

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

from ..recordings import list_recordings, load_stack
from .detection import detect, detection_files, mean_recording, roi_trace
from .plots import ImageView, TraceView

VIEW_RESPONSE = "Response (dF/F)"
VIEW_BASELINE = "Baseline image"


class SettingsPreview(QGroupBox):
    """Shows the automatic ROI, the electrode mask and the ROI trace of an example folder.

    Call `show_folders` when the choice of folders changes and `show_settings`
    when a setting changes. Nothing is saved; this is only for looking.
    """

    def __init__(self):
        super().__init__("Example: what these settings find")
        self.settings = None
        self.load = lru_cache(maxsize=4)(load_stack)
        self.mean_of = lru_cache(maxsize=2)(self._mean_of)

        self.folder_box = QComboBox()
        self.folder_box.setToolTip("The recording folder used as the example.")
        self.folder_box.currentIndexChanged.connect(self.redraw)
        self.view_box = QComboBox()
        self.view_box.addItems([VIEW_RESPONSE, VIEW_BASELINE])
        self.view_box.setToolTip("The baseline image shows the electrode best.")
        self.view_box.currentIndexChanged.connect(self.redraw)
        self.image = ImageView(figsize=(4.3, 3.2))
        self.image.tool = None  # only for looking
        self.trace = TraceView(figsize=(4.3, 2.5))
        self.message = QLabel("Choose a recordings folder to see an example.")
        self.message.setWordWrap(True)

        choices = QHBoxLayout()
        choices.addWidget(self.folder_box, 1)
        choices.addWidget(self.view_box)
        layout = QVBoxLayout(self)
        layout.addLayout(choices)
        layout.addWidget(self.image, 5)
        layout.addWidget(self.trace, 4)
        layout.addWidget(self.message)
        # Large enough to read, also when the dialog is short because all settings sections are closed.
        self.setMinimumWidth(430)
        self.image.setMinimumHeight(290)
        self.trace.setMinimumHeight(220)

    def _mean_of(self, paths):
        return mean_recording(paths, self.load)

    def show_folders(self, recordings_folder, folders, example=None):
        """Offer these recording folders as examples.

        The folder on show stays on show if it is still offered. Otherwise
        `example` is shown, or else the first folder. Call `show_settings` or
        `redraw` afterwards.
        """
        on_show = self.folder_box.currentData()
        self.folder_box.blockSignals(True)
        self.folder_box.clear()
        for folder in folders:
            name = folder.relative_to(recordings_folder).as_posix()
            self.folder_box.addItem(folder.name if name == "." else name, folder)
        for choice in (example, on_show):
            if choice in folders:
                self.folder_box.setCurrentIndex(folders.index(choice))
        self.folder_box.blockSignals(False)

    def show_settings(self, settings):
        self.settings = settings
        self.redraw()

    def show_message(self, text):
        """Show a sentence instead of the example, for instance why there is none."""
        self.message.setText(text)

    def redraw(self):
        folder = self.folder_box.currentData()
        if folder is None or self.settings is None:
            return self.show_message("No recording folder to show as an example.")
        paths = detection_files(list_recordings(folder), self.settings)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if not paths:
                raise ValueError("This folder has no stimulated recordings to find the ROI from.")
            stack = self.mean_of(tuple(paths))
            found = detect(stack, self.settings)
            trace = roi_trace(stack, found.center, self.settings.roi_radius_px, self.settings)
        except (OSError, ValueError) as error:
            return self.show_message(f"⚠ {error}")
        finally:
            QApplication.restoreOverrideCursor()

        if self.view_box.currentText() == VIEW_RESPONSE:
            self.image.show_image(found.response * 100, "Response at the peak, dF/F (%)")
        else:
            self.image.show_image(found.baseline, "Baseline brightness, F0 (counts)", "gray")
        self.image.show_roi(found.center, self.settings.roi_radius_px)
        self.image.show_electrode(found.electrode)
        used = ", ".join(path.stem for path in paths)
        self.trace.show_trace(trace, self.settings, f"Mean of {used}", found.peak_frame)
        response = round(found.peak_response * 100, 2)
        warning = "  ⚠ low response" if response < self.settings.low_response_percent else ""
        self.show_message(
            f"ROI centre ({found.center[0]}, {found.center[1]}), response there {response:.1f} %{warning}.  "
            f"Electrode: {int(found.electrode.sum())} pixels."
        )
