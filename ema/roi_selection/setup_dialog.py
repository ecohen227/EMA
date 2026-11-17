"""The dialog that starts ROI Selection: recordings folder, settings, output folder."""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..recordings import find_recording_folders
from ..user_settings import remember, remembered
from ..widgets import FolderFilter, FolderInput, SettingsForm, hint, is_inside
from .preview import SettingsPreview
from ..recordings import folder_matches
from .selections import FILE_NAME, Selections
from .settings import RoiSettings

class RoiSettingsForm(SettingsForm):
    """The ROI settings, in two columns. The electrode settings are greyed out while the electrode is not looked for."""

    def __init__(self, settings):
        super().__init__(RoiSettings, right=("Electrode", "Display"))
        self.inputs["find_electrode"].toggled.connect(self.grey_out_electrode_settings)
        self.show_settings(settings)

    def show_settings(self, settings):
        super().show_settings(settings)
        self.grey_out_electrode_settings()

    def grey_out_electrode_settings(self):
        wanted = self.inputs["find_electrode"].isChecked()
        for name in self.inputs:
            if name.startswith("electrode_"):
                self.inputs[name].setEnabled(wanted)
                self.labels[name].setEnabled(wanted)


class SetupDialog(QDialog):
    """Asks for the recordings folder, the settings and the output folder.

    After it is accepted, `selections` and `output_folder` hold the result.
    Selections already saved in the output folder are loaded and continued.
    Pass `selections` to only change the settings of a session that is running.
    An example on the right shows what the settings find; `example_folder`
    is the recording folder it starts with.
    """

    def __init__(self, parent=None, selections=None, output_folder=None, example_folder=None):
        super().__init__(parent)
        self.setWindowTitle("ROI Selection – setup")
        self.selections = selections
        self.output_folder = output_folder
        running = selections is not None

        self.recordings = FolderInput(
            "Select the recordings folder",
            str(selections.recordings_folder) if running else remembered("roi_recordings_folder"),
        )
        self.output = FolderInput(
            "Select the output folder", str(output_folder) if running else remembered("roi_output_folder")
        )
        self.recordings.setEnabled(not running)
        self.output.setEnabled(not running)
        self.output.changed.connect(self.show_saved_settings)
        self.filter = FolderFilter()
        if running:
            self.filter.show_words(selections.only_folders_with, selections.skip_folders_with)
        self.filter.changed.connect(self.show_matching_folders)
        self.match_count = QLabel()
        self.all_folders = []  # every recording folder under the recordings folder
        self.searched_folder = None  # the folder `all_folders` was found in
        self.form = RoiSettingsForm(selections.settings if running else RoiSettings())
        self.note = QLabel()
        self.note.setWordWrap(True)

        self.preview = SettingsPreview()
        self.example_folder = example_folder
        self.recordings.changed.connect(self.find_folders)
        # The example is redrawn a moment after the last edit, not on every keystroke.
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(300)
        self.preview_timer.timeout.connect(self.show_example)
        self.form.changed.connect(lambda _: self.preview_timer.start())

        defaults = QPushButton("Restore the defaults")
        defaults.clicked.connect(lambda: self.form.show_settings(RoiSettings()))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Apply" if running else "Start")
        buttons.addButton(defaults, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        steps = QVBoxLayout()
        steps.addWidget(self._step("1.  Recordings folder", "Every folder inside it that holds TIFF movies is listed, unless you narrow it down here.", self.recordings, self.filter, self.match_count))
        steps.addWidget(self._step("2.  Settings", "The defaults suit the standard recordings. Click a heading to see or change its settings; the example on the right follows your changes.", self.form))
        steps.addWidget(self._step("3.  Output folder", f"The selections are saved here as {FILE_NAME}. Nothing is ever written into the recordings folder.", self.output))
        steps.addWidget(self.note)
        steps.addStretch()
        steps.addWidget(buttons)
        layout = QHBoxLayout(self)
        layout.addLayout(steps)
        layout.addWidget(self.preview, 1)
        self.show_saved_settings()
        self.find_folders()

    def find_folders(self):
        """Look up the recording folders of the chosen recordings folder."""
        recordings = self.recordings.folder()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.all_folders = find_recording_folders(recordings) if recordings and recordings.is_dir() else []
            self.searched_folder = recordings  # the folder `all_folders` was found in
        finally:
            QApplication.restoreOverrideCursor()
        self.show_matching_folders()

    def matching_folders(self):
        """The recording folders that pass the folder filter."""
        only_with, skip_with = self.filter.words()
        return [
            folder
            for folder in self.all_folders
            if folder_matches(folder.relative_to(self.searched_folder).as_posix(), only_with, skip_with)
        ]

    def show_matching_folders(self):
        """Say how many folders pass the filter, and offer those as examples."""
        if self.searched_folder is None:  # the folders are not looked up yet
            return
        matching = self.matching_folders()
        if self.all_folders:
            self.match_count.setText(f"{len(matching)} of {len(self.all_folders)} recording folders will be used.")
        else:
            self.match_count.setText("")
        self.preview.show_folders(self.searched_folder, matching, self.example_folder)
        self.example_folder = None  # only the first list starts on it; later the folder on show stays
        self.show_example()

    def show_example(self):
        settings = self.form.settings()
        if settings.problems():
            self.preview.show_message("⚠ " + " ".join(settings.problems()))
        else:
            self.preview.show_settings(settings)

    def _step(self, title, explanation, *widgets):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(hint(explanation))
        for widget in widgets:
            layout.addWidget(widget)
        return box

    def saved_file(self):
        folder = self.output.folder()
        return folder / FILE_NAME if folder else None

    def show_saved_settings(self):
        """When the output folder already holds selections, show the settings they were made with."""
        file = self.saved_file()
        if self.selections is not None or file is None or not file.is_file():
            self.note.clear()
            return
        try:
            saved = Selections.load(file)
        except (OSError, ValueError) as error:
            self.note.setText(f"⚠ The {FILE_NAME} in the output folder cannot be read: {error}")
            return
        self.form.show_settings(saved.settings)
        self.filter.show_words(saved.only_folders_with, saved.skip_folders_with)
        self.note.setText(
            f"The output folder already holds selections for {len(saved.folders)} folder(s). They will be "
            "continued, and their settings and folder filter are shown above. If you change a setting, every "
            "folder has to be reviewed again; what you set by hand is kept."
        )

    def accept(self):
        settings = self.form.settings()
        recordings, output = self.recordings.folder(), self.output.folder()
        problems = settings.problems()
        if recordings is None or not recordings.is_dir():
            problems.append("Choose an existing recordings folder.")
        if output is None:
            problems.append("Choose an output folder.")
        elif recordings is not None and is_inside(output, recordings):
            problems.append("The output folder must be outside the recordings folder, so the recordings stay untouched.")
        if problems:
            QMessageBox.warning(self, "Please check", "\n\n".join(problems))
            return

        selections = self.selections or self._load_or_start(recordings, output)
        if selections is None or not self._agrees_to_losses(selections, settings):
            return
        if self.selections is None:
            self.selections, self.output_folder = selections, output
            remember(roi_recordings_folder=str(recordings), roi_output_folder=str(output))
        selections.change_settings(settings)
        selections.change_folder_filter(*self.filter.words())
        super().accept()

    def _agrees_to_losses(self, selections, settings):
        """Ask before reviews or saved folders are lost. True if nothing is lost or the user agrees."""
        reviewed = sum(selection.reviewed for selection in selections.folders.values())
        left_out = [name for name in selections.folders if not folder_matches(name, *self.filter.words())]
        losses = []
        if settings != selections.settings and reviewed:
            losses.append(
                f"The settings have changed, so all {reviewed} reviewed folder(s) will have to be reviewed again. "
                "What you set by hand is kept."
            )
        if left_out:
            losses.append(f"{len(left_out)} saved folder(s) do not pass the folder filter and will be removed from the ROI file.")
        if not losses:
            return True
        answer = QMessageBox.question(self, "Please confirm", "\n\n".join(losses) + "\n\nContinue?")
        return answer == QMessageBox.Yes

    def _load_or_start(self, recordings, output):
        """The selections saved in the output folder, or new ones. None if the user backs out."""
        file = output / FILE_NAME
        if not file.is_file():
            output.mkdir(parents=True, exist_ok=True)
            return Selections(recordings)
        try:
            saved = Selections.load(file)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot read the saved selections", f"{file}\n\n{error}\n\nChoose another output folder.")
            return None
        if saved.recordings_folder.resolve() != recordings.resolve():
            answer = QMessageBox.question(
                self,
                "Different recordings folder",
                f"The selections in the output folder were made for\n{saved.recordings_folder}\n\n"
                f"Use them for\n{recordings}?\n\nChoose Yes only if this is the same data in a new place.",
            )
            if answer != QMessageBox.Yes:
                return None
            saved.recordings_folder = recordings
        return saved
