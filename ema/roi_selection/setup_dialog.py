"""The dialog that starts ROI Selection: recordings folder, settings, output folder."""

from dataclasses import fields
from pathlib import Path

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..user_settings import remember, remembered
from .selections import FILE_NAME, Selections
from .settings import RoiSettings

MAX_FRAME = 1_000_000


class SettingsForm(QWidget):
    """One input per setting, grouped in boxes. Built from the list in settings.py."""

    def __init__(self, settings):
        super().__init__()
        self.inputs = {}
        columns = QHBoxLayout(self)
        columns.setContentsMargins(0, 0, 0, 0)
        left, right = QVBoxLayout(), QVBoxLayout()
        columns.addLayout(left)
        columns.addLayout(right)

        forms = {}
        for f in fields(RoiSettings):
            details = f.metadata
            if details["group"] not in forms:
                box = QGroupBox(details["group"])
                forms[details["group"]] = QFormLayout(box)
                (right if details["group"] == "Electrode" else left).addWidget(box)
            widget = self._make_input(details)
            widget.setToolTip(details["help"])
            label = QLabel(details["label"] + ":")
            label.setToolTip(details["help"])
            forms[details["group"]].addRow(label, widget)
            self.inputs[f.name] = widget
        left.addStretch()
        right.addStretch()
        self.show_settings(settings)

    def _make_input(self, details):
        kind = details["kind"]
        if kind == "bool":
            return QCheckBox()
        if kind == "choice":
            box = QComboBox()
            box.addItems(details["choices"])
            return box
        if kind == "names":
            return QLineEdit()
        if kind == "frames":
            return FrameRange()
        box = QSpinBox() if kind == "int" else QDoubleSpinBox()
        box.setRange(details["minimum"], details["maximum"])
        if kind == "float":
            box.setSingleStep(details["step"])
        box.setSuffix(" " + details["unit"])
        return box

    def show_settings(self, settings):
        for f in fields(RoiSettings):
            widget, value, kind = self.inputs[f.name], getattr(settings, f.name), f.metadata["kind"]
            if kind == "bool":
                widget.setChecked(value)
            elif kind == "choice":
                widget.setCurrentText(value)
            elif kind == "names":
                widget.setText(", ".join(value))
            else:
                widget.setValue(value)

    def settings(self):
        values = {}
        for f in fields(RoiSettings):
            widget, kind = self.inputs[f.name], f.metadata["kind"]
            if kind == "bool":
                values[f.name] = widget.isChecked()
            elif kind == "choice":
                values[f.name] = widget.currentText()
            elif kind == "names":
                names = [name.strip() for name in widget.text().split(",")]
                values[f.name] = [name.removesuffix(".tif") for name in names if name]
            else:
                values[f.name] = widget.value()
        return RoiSettings(**values)


class FrameRange(QWidget):
    """Two numbers: the first frame of a window and the frame it ends before."""

    def __init__(self):
        super().__init__()
        self.first, self.last = QSpinBox(), QSpinBox()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for text, box in (("from", self.first), ("up to", self.last)):
            box.setRange(0, MAX_FRAME)
            layout.addWidget(QLabel(text))
            layout.addWidget(box, 1)

    def setValue(self, frames):
        self.first.setValue(frames[0])
        self.last.setValue(frames[1])

    def value(self):
        return [self.first.value(), self.last.value()]


class FolderInput(QWidget):
    """A folder path with a Browse button."""

    def __init__(self, title, folder=""):
        super().__init__()
        self.title = title
        self.path = QLineEdit(folder)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.path, 1)
        layout.addWidget(browse)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, self.title, self.path.text())
        if folder:
            self.path.setText(folder)

    def folder(self):
        text = self.path.text().strip()
        return Path(text) if text else None


class SetupDialog(QDialog):
    """Asks for the recordings folder, the settings and the output folder.

    After it is accepted, `selections` and `output_folder` hold the result.
    Selections already saved in the output folder are loaded and continued.
    Pass `selections` to only change the settings of a session that is running.
    """

    def __init__(self, parent=None, selections=None, output_folder=None):
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
        self.output.path.editingFinished.connect(self.show_saved_settings)
        self.form = SettingsForm(selections.settings if running else RoiSettings())
        self.note = QLabel()
        self.note.setWordWrap(True)

        defaults = QPushButton("Restore defaults")
        defaults.clicked.connect(lambda: self.form.show_settings(RoiSettings()))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Apply" if running else "Start")
        buttons.addButton(defaults, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._step("1.  Recordings folder", "Every folder inside it that holds TIFF movies is listed.", self.recordings))
        layout.addWidget(self._step("2.  Settings", "Hover over a setting for an explanation. The defaults suit the standard recordings.", self.form))
        layout.addWidget(self._step("3.  Output folder", f"The selections are saved here as {FILE_NAME}. Nothing is ever written into the recordings folder.", self.output))
        layout.addWidget(self.note)
        layout.addWidget(buttons)
        self.show_saved_settings()

    def _step(self, title, explanation, widget):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        hint = QLabel(explanation)
        hint.setStyleSheet("color: gray")
        layout.addWidget(hint)
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
        except (OSError, ValueError, KeyError) as error:
            self.note.setText(f"⚠ The {FILE_NAME} in the output folder cannot be read: {error}")
            return
        self.form.show_settings(saved.settings)
        self.note.setText(
            f"The output folder already holds selections for {len(saved.folders)} folder(s). They will be "
            "continued, and their settings are shown above. If you change a setting, folders you adjusted "
            "by hand are kept and all others are detected again."
        )

    def accept(self):
        settings = self.form.settings()
        recordings, output = self.recordings.folder(), self.output.folder()
        problems = settings.problems()
        if recordings is None or not recordings.is_dir():
            problems.append("Choose an existing recordings folder.")
        if output is None:
            problems.append("Choose an output folder.")
        elif recordings is not None and _is_inside(output, recordings):
            problems.append("The output folder must be outside the recordings folder, so the recordings stay untouched.")
        if problems:
            QMessageBox.warning(self, "Please check", "\n\n".join(problems))
            return

        if self.selections is None:
            selections = self._load_or_start(recordings, output)
            if selections is None:
                return
            self.selections, self.output_folder = selections, output
            remember(roi_recordings_folder=str(recordings), roi_output_folder=str(output))
        self.selections.change_settings(settings)
        super().accept()

    def _load_or_start(self, recordings, output):
        """The selections saved in the output folder, or new ones. None if the user backs out."""
        file = output / FILE_NAME
        if not file.is_file():
            output.mkdir(parents=True, exist_ok=True)
            return Selections(recordings)
        try:
            saved = Selections.load(file)
        except (OSError, ValueError, KeyError) as error:
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


def _is_inside(folder, parent):
    folder, parent = folder.resolve(), parent.resolve()
    return folder == parent or parent in folder.parents
