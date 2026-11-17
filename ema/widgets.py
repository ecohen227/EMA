"""Widgets the EMA windows share: hints, file and folder inputs, the folder filter, settings forms, check lists of
measures, and the library bar of the two configurators."""

from dataclasses import fields
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .library import file_name
from .user_settings import remember, remembered

WARNING_COLOUR, ERROR_COLOUR, OK_COLOUR = "#b35c00", "#c1121f", "#1a7f37"
MAX_FRAME = 1_000_000


def hint(text=""):
    """A grey line of explanation."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray")
    return label


def coloured(text, colour):
    return f"<span style='color:{colour}'>{text}</span>"


def is_inside(folder, parent):
    """True if `folder` is `parent` or inside it."""
    folder, parent = Path(folder).resolve(), Path(parent).resolve()
    return folder == parent or parent in folder.parents


def choose(parent, title, text, *choices):
    """Ask a question with a button for each choice and a Cancel button; the first choice is the default.

    Returns the chosen text, or None for Cancel.
    """
    box = QMessageBox(QMessageBox.Question, title, text, parent=parent)
    buttons = [box.addButton(choice, QMessageBox.AcceptRole) for choice in choices]
    box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(buttons[0])
    box.exec_()
    clicked = box.clickedButton()
    return choices[buttons.index(clicked)] if clicked in buttons else None


def scrolled(widget):
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    return area


def with_unit(name, unit):
    """A measure's name with its unit, leaving out units that only repeat the name ('tail fraction', not
    'tail fraction (fraction)')."""
    if not unit or unit in ("fraction", "ratio", "count") or unit in name.split():
        return name
    return f"{name} ({unit})"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class PathInput(QWidget):
    """A path with a Browse button. `changed` is emitted when another path is typed or picked (leaving the field
    without changing it is not a change)."""

    changed = pyqtSignal()

    def __init__(self, title, path=""):
        super().__init__()
        self.title = title
        self.path = QLineEdit(path)
        self.reported = path
        self.path.editingFinished.connect(self._typed)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.path, 1)
        layout.addWidget(browse)

    def _typed(self):
        if self.path.text() != self.reported:
            self._report()

    def _report(self):
        self.reported = self.path.text()
        self.changed.emit()

    def set_path(self, path):
        """Show a path without reporting it as a change."""
        self.path.setText(str(path))
        self.reported = self.path.text()


class FolderInput(PathInput):
    """A folder path with a Browse button."""

    def __init__(self, title, folder=""):
        super().__init__(title, folder)

    def browse(self):
        folder =QFileDialog.getExistingDirectory(self, self.title, self.path.text())
        if folder:
            self.path.setText(folder)
            self._report()

    def folder(self):
        text = self.path.text().strip()
        return Path(text) if text else None


class FileInput(PathInput):
    """A file path with a Browse button."""

    def __init__(self, title, file_filter, path=""):
        super().__init__(title, path)
        self.file_filter = file_filter

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, self.title, self.path.text(), self.file_filter)
        if path:
            self.path.setText(path)
            self._report()

    def file(self):
        text = self.path.text().strip()
        return Path(text) if text else None


class FolderFilter(QWidget):
    """Two lists of words that choose which recording folders are used."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.only_with, self.skip_with = QLineEdit(), QLineEdit()
        self.only_with.setPlaceholderText("all folders")
        self.only_with.setToolTip("Words separated by commas, for example: 11p\n"
                                  "Only folders with at least one of these words in their path are used. Leave empty to "
                                  "use all.")
        self.skip_with.setPlaceholderText("none")
        self.skip_with.setToolTip("Words separated by commas, for example: 4ap, wash\n"
                                  "Folders with one of these words in their path are left out.")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for text, box in (("Only folders with:", self.only_with), ("Skip folders with:", self.skip_with)):
            box.textChanged.connect(self.changed)
            layout.addWidget(QLabel(text))
            layout.addWidget(box, 1)

    def show_words(self, only_with, skip_with):
        self.only_with.setText(", ".join(only_with))
        self.skip_with.setText(", ".join(skip_with))

    def words(self):
        """The two lists of words: (only folders with, skip folders with)."""
        return tuple([word.strip() for word in box.text().split(",") if word.strip()]
                     for box in (self.only_with, self.skip_with))


class FrameRange(QWidget):
    """Two numbers: the first frame of a window and the frame it ends before."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.first, self.last = QSpinBox(), QSpinBox()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for text, box in (("from", self.first), ("up to", self.last)):
            box.setRange(0, MAX_FRAME)
            box.valueChanged.connect(self.changed)
            layout.addWidget(QLabel(text))
            layout.addWidget(box, 1)

    def setValue(self, frames):  # noqa: N802  (named like Qt's inputs)
        self.first.setValue(frames[0])
        self.last.setValue(frames[1])

    def value(self):
        return [self.first.value(), self.last.value()]


# ---------------------------------------------------------------------------
# Settings forms
# ---------------------------------------------------------------------------


class Section(QWidget):
    """A group of settings under a heading. Clicking the heading shows or hides the settings."""

    def __init__(self, title):
        super().__init__()
        self.title = title
        self.heading = QToolButton()
        self.heading.setText(title)
        self.heading.setCheckable(True)
        self.heading.setAutoRaise(True)
        self.heading.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.heading.setToolTip("Click to show or hide these settings.")
        self.heading.toggled.connect(self.show_settings)
        self.content = QFrame()
        self.content.setFrameShape(QFrame.StyledPanel)
        self.form = QFormLayout(self.content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.heading)
        layout.addWidget(self.content)
        self.show_settings(False)

    def show_settings(self, shown):
        self.content.setVisible(shown)
        self.heading.setArrowType(Qt.DownArrow if shown else Qt.RightArrow)

    def show_note(self, note):
        """Put a short remark after the title, or remove it with an empty text."""
        self.heading.setText(f"{self.title}   ({note})" if note else self.title)


ADVANCED = "Advanced: change only if you know why"


class SettingsForm(QWidget):
    """One input per setting of a settings class (see ema.definitions), in sections that open on a click.

    The sections start closed, because the defaults suit most recordings. A
    closed section says in its heading how many of its settings are not at
    their default. Settings marked advanced are gathered in one last section,
    under the name of their own section. The sections named in `right` go in a
    second column.
    """

    changed = pyqtSignal(str)  # the name of the setting that was edited

    def __init__(self, settings_class, groups=None, right=()):
        super().__init__()
        self.settings_class = settings_class
        self.inputs, self.labels, self.sections, self.placed = {}, {}, {}, {}
        groups = groups or list(dict.fromkeys(f.metadata["group"] for f in fields(settings_class)))
        columns = QHBoxLayout(self)
        columns.setContentsMargins(0, 0, 0, 0)
        left_column, right_column = QVBoxLayout(), QVBoxLayout()
        columns.addLayout(left_column, 1)
        if right:
            columns.addLayout(right_column, 1)
        for group in groups:
            self.sections[group] = Section(group)
            (right_column if group in right else left_column).addWidget(self.sections[group])
        advanced = Section(ADVANCED)
        left_column.addWidget(advanced)
        headed = set()
        for f in fields(settings_class):
            details = f.metadata
            section = advanced if details.get("advanced") else self.sections[details["group"]]
            if section is advanced and details["group"] not in headed:
                headed.add(details["group"])
                advanced.form.addRow(QLabel(f"<b>{details['group']}</b>"))
            widget = self._make_input(f.name, details)
            label = QLabel(details["label"] + ":")
            for item in (widget, label):
                item.setToolTip(details["help"])
            section.form.addRow(label, widget)
            self.inputs[f.name], self.labels[f.name] = widget, label
            self.placed.setdefault(section.title, []).append(f.name)
        self.sections[ADVANCED] = advanced
        for title in list(self.sections):
            if title not in self.placed:  # a section without settings is not shown
                self.sections.pop(title).hide()
        left_column.addStretch()
        right_column.addStretch()

    def _make_input(self, name, details):
        kind = details["kind"]
        if kind == "bool":
            box = QCheckBox()
            box.toggled.connect(lambda _: self._edited(name))
        elif kind == "choice":
            box = QComboBox()
            box.addItems(details["choices"])
            box.currentTextChanged.connect(lambda _: self._edited(name))
        elif kind == "names":
            box = QLineEdit()
            box.setPlaceholderText("none")
            box.editingFinished.connect(lambda: self._edited(name))
        elif kind == "frames":
            box = FrameRange()
            box.changed.connect(lambda: self._edited(name))
        else:
            box = QSpinBox() if kind == "int" else QDoubleSpinBox()
            box.setRange(details["minimum"], details["maximum"])
            if kind == "float":
                box.setDecimals(3 if details.get("step", 1) < 0.01 else 2)
                box.setSingleStep(details.get("step", 1.0))
            if details["unit"]:
                box.setSuffix(" " + details["unit"])
            box.setKeyboardTracking(False)  # report a typed number when it is complete, not every digit
            box.valueChanged.connect(lambda _: self._edited(name))
        return box

    def _edited(self, name):
        self.show_changes()
        self.changed.emit(name)

    def show_settings(self, settings):
        for f in fields(self.settings_class):
            widget, value, kind = self.inputs[f.name], getattr(settings, f.name), f.metadata["kind"]
            widget.blockSignals(True)
            if kind == "bool":
                widget.setChecked(value)
            elif kind == "choice":
                widget.setCurrentText(value)
            elif kind == "names":
                widget.setText(", ".join(value))
            else:
                widget.setValue(value)
            widget.blockSignals(False)
        self.show_changes()

    def settings(self):
        values = {}
        for f in fields(self.settings_class):
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
        return self.settings_class(**values)

    def show_changes(self):
        """Say in each section's heading how many of its settings are not at their default."""
        settings, defaults = self.settings(), self.settings_class()
        for title, names in self.placed.items():
            changed = sum(getattr(settings, name) != getattr(defaults, name) for name in names)
            self.sections[title].show_note(f"{changed} changed from the default" if changed else "")


# ---------------------------------------------------------------------------
# Check lists of measures
# ---------------------------------------------------------------------------


class Checklist(QWidget):
    """Tick boxes for the measures of a catalogue (see ema.definitions.Measure), in groups, with All and None."""

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
            box = QCheckBox(with_unit(measure.key, measure.unit))
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


# ---------------------------------------------------------------------------
# The library bar of the configurators
# ---------------------------------------------------------------------------


class LibraryBar(QWidget):
    """The bar at the top of a configurator: the protocols or detectors of a library, with Save, Save as, Delete,
    Import and Export (and New, when the configurator makes new ones from a form).

    `item` is the protocol or detector on show; the configurator edits it in
    place and calls `changed()` after each edit. `shown` is emitted when
    another one is put on show. Built-in ones are never changed: they are
    saved under a new name.
    """

    shown = pyqtSignal()

    def __init__(self, library, new=None):
        super().__init__()
        self.library = library
        self.noun = library.noun
        self.new_item = new  # new(parent) -> a new protocol or detector, or None
        self.entries = []
        self.item = self.entry = self.saved = None  # saved: the item as last saved, to tell whether it changed
        self.box = QComboBox()
        self.box.setMinimumWidth(260)
        self.box.activated.connect(self.choose)
        actions = [("Save", f"Save the changes. A built-in {self.noun} is saved under a new name.", self.save),
                   ("Save as…", f"Save as a new {self.noun}.", self.save_as),
                   ("Delete", f"Delete this {self.noun} from the library.", self.delete),
                   ("Import…", f"Add a {self.noun} file to the library.", self.import_file),
                   ("Export…", f"Save a copy of this {self.noun} anywhere, for example to share it.", self.export)]
        if new is not None:
            actions.insert(0, ("New…", f"Make a new {self.noun} from a form.", self.new))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(self.noun.capitalize() + ":"))
        layout.addWidget(self.box)
        self.buttons = {}
        for text, tip, action in actions:
            button = self.buttons[text] = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(lambda _, act=action: act())
            layout.addWidget(button)
        self.state = QLabel()
        layout.addWidget(self.state, 1)

    # --- what is on show ---

    @property
    def unsaved(self):
        return self.item is not None and (self.saved is None or self.item.to_dict() != self.saved)

    def open(self, index=0):
        """Show the entry at `index`, or the first one that can be read. True if one was shown."""
        self.entries = self.library.entries()
        for entry in self.entries[index:] + self.entries[:index]:
            try:
                item = self.library.load(entry.path)
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Cannot open", f"{entry.path}\n\n{error}")
                continue
            self.show_item(item, entry)
            return True
        return False

    def show_item(self, item, entry):
        """Put a protocol or detector on show; `entry` None for one that was never saved."""
        self.item, self.entry = item, entry
        self.saved = item.to_dict() if entry else None
        self.buttons["Delete"].setEnabled(entry is not None and not entry.built_in)
        self.fill()
        self.shown.emit()
        self.changed()

    def fill(self):
        """List the library, with the one on show selected (or added at the end if it was never saved)."""
        self.entries = self.library.entries()
        labels = [entry.label for entry in self.entries]
        index = next((i for i, e in enumerate(self.entries) if self.entry and e.path == self.entry.path), None)
        if index is None:
            labels.append(f"{self.item.name}  (not saved)")
            index = len(labels) - 1
        self.box.blockSignals(True)
        self.box.clear()
        self.box.addItems(labels)
        self.box.setCurrentIndex(index)
        self.box.blockSignals(False)

    def changed(self):
        """Show whether the one on show has changes that are not saved."""
        self.state.setText(coloured("  –  changes not saved", WARNING_COLOUR) if self.unsaved else "")

    def choose(self, index):
        if index >= len(self.entries) or self.entries[index] == self.entry or not self.may_leave():
            self.fill()
            return
        self.open(index)

    def may_leave(self):
        """True if there are no unsaved changes, or the user saves or discards them."""
        if not self.unsaved:
            return True
        answer = QMessageBox.question(self, "Unsaved changes", f"Save the changes to {self.item.name}?",
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if answer == QMessageBox.Save:
            return self.save()
        return answer == QMessageBox.Discard

    def message(self, text):
        window = self.window()
        if isinstance(window, QMainWindow):
            window.statusBar().showMessage(text, 6000)

    # --- the buttons ---

    def ask_name(self, title, suggestion):
        """A name the library does not use yet, or None if the user cancels."""
        while True:
            name, accepted = QInputDialog.getText(self, title, f"Name of the {self.noun}:", text=suggestion)
            name = name.strip()
            if not accepted:
                return None
            if not name:
                QMessageBox.information(self, title, f"Give the {self.noun} a name.")
            elif not self.library.is_taken(name):
                return name
            else:
                QMessageBox.information(self, title, f"There is already a {self.noun} called {name}. Choose another name.")
            suggestion = name

    def new(self):
        if not self.may_leave():
            return
        item = self.new_item(self)
        if item is None:
            return
        if self.library.is_taken(item.name):
            name = self.ask_name(f"New {self.noun}", f"{item.name} 2")
            if not name:
                return
            item.name = name
        self.show_item(item, None)

    def save(self):
        """Save into the library. True if it was saved."""
        if self.entry is None or self.entry.built_in:
            return self.save_as()
        if self.library.is_taken(self.item.name, except_path=self.entry.path):
            QMessageBox.information(self, "Save", f"There is already a {self.noun} called {self.item.name}. Change its "
                                                  "name or use Save as….")
            return False
        return self._store(replacing=self.entry.path)

    def save_as(self):
        suggestion = self.item.name
        if self.library.is_taken(suggestion):
            suggestion = f"{suggestion} (mine)"
        name = self.ask_name("Save as", suggestion)
        if not name:
            return False
        self.item.name = name
        return self._store(replacing=None)

    def _store(self, replacing):
        problems = self.item.problems()
        if problems:
            QMessageBox.warning(self, "Cannot save yet", "Please fix these first:\n\n• " + "\n• ".join(problems))
            return False
        try:
            path = self.library.save(self.item, replacing)
        except OSError as error:
            QMessageBox.warning(self, "Cannot save", str(error))
            return False
        entry = next(e for e in self.library.entries() if e.path == path)
        self.show_item(self.item, entry)
        self.message(f"Saved {self.item.name} in the {self.noun} library.")
        return True

    def delete(self):
        if self.entry is None or self.entry.built_in:
            return
        answer = QMessageBox.question(self, "Delete", f"Delete the {self.noun} {self.entry.name} from the library?\n"
                                                      "This cannot be undone.")
        if answer != QMessageBox.Yes:
            return
        try:
            self.library.delete(self.entry)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot delete", str(error))
            return
        self.saved = self.item.to_dict()  # nothing left to save
        self.open(0)

    def import_file(self):
        if not self.may_leave():
            return
        key = f"{self.noun}_files_folder"
        path, _ = QFileDialog.getOpenFileName(self, f"Import a {self.noun}", remembered(key),
                                              f"{self.noun.capitalize()} files (*.json)")
        if not path:
            return
        remember(**{key: str(Path(path).parent)})
        try:
            item = self.library.load(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot import", f"{path}\n\n{error}")
            return
        if self.library.is_taken(item.name):
            name = self.ask_name("Import", f"{item.name} (imported)")
            if not name:
                return
            item.name = name
        self.show_item(item, None)
        self._store(replacing=None)

    def export(self):
        key = f"{self.noun}_files_folder"
        suggestion = Path(remembered(key) or Path.home()) / file_name(self.item.name, self.noun)
        path, _ = QFileDialog.getSaveFileName(self, f"Export the {self.noun}", str(suggestion),
                                              f"{self.noun.capitalize()} files (*.json)")
        if not path:
            return
        try:
            self.item.save(path)
        except OSError as error:
            QMessageBox.warning(self, "Cannot export", str(error))
            return
        remember(**{key: str(Path(path).parent)})
        self.message(f"Exported to {path}.")
