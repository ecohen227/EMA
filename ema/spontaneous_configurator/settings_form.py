"""A form for a settings dataclass whose fields carry their label, group, unit and help (see roi_selection/settings.py)."""

from dataclasses import fields

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QDoubleSpinBox, QLabel, QSpinBox, QVBoxLayout, QWidget

from ..roi_selection.setup_dialog import FrameRange, Section


class SettingsForm(QWidget):
    """One input per setting, in sections that open on a click; a closed section says how many of its settings changed."""

    changed = pyqtSignal(str)  # the name of the setting that was edited

    def __init__(self, settings_class, groups):
        super().__init__()
        self.settings_class = settings_class
        self.inputs, self.sections = {}, {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for group in groups:
            self.sections[group] = Section(group)
            layout.addWidget(self.sections[group])
        layout.addStretch()
        for f in fields(settings_class):
            details = f.metadata
            widget = self._make_input(f.name, details)
            tip = details["help"]
            widget.setToolTip(tip)
            label = QLabel(details["label"] + ":")
            label.setToolTip(tip)
            self.sections[details["group"]].form.addRow(label, widget)
            self.inputs[f.name] = widget

    def _make_input(self, name, details):
        kind = details["kind"]
        if kind == "bool":
            box = QCheckBox()
            box.toggled.connect(lambda _: self._edited(name))
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
            widget, value = self.inputs[f.name], getattr(settings, f.name)
            widget.blockSignals(True)
            if f.metadata["kind"] == "bool":
                widget.setChecked(value)
            else:
                widget.setValue(value)
            widget.blockSignals(False)
        self.show_changes()

    def settings(self):
        values = {}
        for f in fields(self.settings_class):
            widget = self.inputs[f.name]
            values[f.name] = widget.isChecked() if f.metadata["kind"] == "bool" else widget.value()
        return self.settings_class(**values)

    def show_changes(self):
        """Say in each section's heading how many of its settings are not at their default."""
        settings, defaults = self.settings(), self.settings_class()
        for group, section in self.sections.items():
            names = [f.name for f in fields(self.settings_class) if f.metadata["group"] == group]
            changed = sum(getattr(settings, name) != getattr(defaults, name) for name in names)
            section.show_note(f"{changed} changed from the default" if changed else "")
