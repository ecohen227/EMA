"""The Kinetics, Spatial, and Comparisons and summary tabs.

The kinetic and spatial check lists are built from the catalogue in
ema/evoked/metrics.py, so a measure added there appears here by itself.
"""

from dataclasses import fields

from PyQt5.QtWidgets import QCheckBox, QDoubleSpinBox, QGridLayout, QLabel, QPushButton, QSpinBox, QWidget

from ..evoked.catalogue import KINETIC, SPATIAL, SpatialSettings
from ..evoked.protocol import (
    DOUBLE,
    PERCENT_SCALE,
    RATIO_SCALE,
    RECOVERY,
    SATURATION,
    SINGLE,
    STATISTICS,
    Comparison,
    ConditionFit,
    Fit,
)
from .editors import Editor
from .widgets import FrameBox, Rows, check_box, choice_box, name_box, remove_button, row_of


class Checklist(QWidget):
    """Check boxes for the metrics of a catalogue, under their group headings, with All and None buttons."""

    def __init__(self, catalogue, on_changed):
        super().__init__()
        self.boxes = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        row, column, group = 0, 0, None
        for metric in catalogue:  # each group under its heading, in two columns
            if metric.group != group:
                group = metric.group
                row += 1 if column else 0
                grid.addWidget(QLabel(f"<i>{group}</i>"), row, 0, 1, 2)
                row, column = row + 1, 0
            box = QCheckBox(f"{metric.key} ({metric.unit})")
            box.setToolTip(metric.explanation.format(pulse="the pulse"))
            box.toggled.connect(on_changed)
            self.boxes[metric.key] = box
            grid.addWidget(box, row, column)
            row, column = (row, 1) if column == 0 else (row + 1, 0)
        row += 1 if column else 0
        everything, nothing = QPushButton("All"), QPushButton("None")
        everything.clicked.connect(lambda: self.set_chosen(list(self.boxes), notify=True))
        nothing.clicked.connect(lambda: self.set_chosen([], notify=True))
        self.on_changed = on_changed
        grid.addWidget(row_of(everything, nothing), row, 0, 1, 2)

    def chosen(self):
        return [key for key, box in self.boxes.items() if box.isChecked()]

    def set_chosen(self, keys, notify=False):
        for key, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(key in keys)
            box.blockSignals(False)
        if notify:
            self.on_changed()


class PulseChoice(QWidget):
    """One check box per pulse of the protocol."""

    def __init__(self, on_changed):
        super().__init__()
        self.on_changed = on_changed
        self.layout_ = QGridLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.boxes = {}

    def show_pulses(self, names, chosen):
        while self.layout_.count():
            widget = self.layout_.takeAt(0).widget()
            widget.setParent(None)
            widget.deleteLater()
        self.boxes = {}
        for index, name in enumerate(names):
            box = QCheckBox(name)
            box.setChecked(name in chosen)
            box.toggled.connect(self.on_changed)
            self.boxes[name] = box
            self.layout_.addWidget(box, index // 8, index % 8)

    def chosen(self):
        return [name for name, box in self.boxes.items() if box.isChecked()]


# ---------------------------------------------------------------------------
# 3. Kinetics
# ---------------------------------------------------------------------------


class KineticsEditor(Editor):
    def __init__(self, units):
        super().__init__(units)
        self.fits = Rows(["Name", "Decay", "Starts", "Start", "Length", ""])
        add_fit = QPushButton("Add fit")
        add_fit.clicked.connect(self.add_fit)
        self.box("Exponential fits", self.fits, row_of(add_fit),
                 explanation="An exponential decay fitted to the trace: single, A·exp(−t/τ) + C, gives τ; double, "
                             "A1·exp(−t/τ1) + A2·exp(−t/τ2) + C, gives a fast and a slow τ and the share of the fast one. "
                             "A fit starts a few frames after the maximum of a pulse, or at a fixed frame. Its stretch is "
                             "the purple band on the plot, which can be dragged.")

        self.checklist = Checklist(KINETIC, self._set_measures)
        self.pulses = PulseChoice(self._set_pulses)
        self.smoothing = QSpinBox()
        self.smoothing.setRange(1, 51)
        self.smoothing.setSuffix(" frames")
        self.smoothing.setKeyboardTracking(False)
        self.smoothing.valueChanged.connect(self._set_smoothing)
        self.box("Time course of each pulse", self.checklist, QLabel("Measured on:"), self.pulses,
                 row_of("Smooth the response over", self.smoothing, "(1 means no smoothing)"),
                 explanation="Measured on the response of each chosen pulse (the trace as a change from its baseline, "
                             "in %), from its stimulus to the end of its peak window. A value is empty when its level is "
                             "not reached inside that stretch, which is common in fast trains.")
        self.content.addStretch()

    def fill(self):
        p = self.protocol
        self.fits.clear()
        starts = [(f"after the maximum of {pulse.name}", pulse.name) for pulse in p.pulses] + [("at a fixed frame", None)]
        for fit in p.fits:
            start, length = FrameBox(self.units, fit.start), FrameBox(self.units, fit.length)
            start.setToolTip("Frames after the maximum (or the frame the fit starts at).")
            start.edited.connect(lambda f=fit, b=start: self._set_fit(f, "start", b.frames()))
            length.edited.connect(lambda f=fit, b=length: self._set_fit(f, "length", b.frames()))
            self.fits.add(
                name_box(fit.name, lambda new, old=fit.name: self.rename(old, new)),
                choice_box([("single", SINGLE), ("double", DOUBLE)], fit.kind, lambda v, f=fit: self._set_fit(f, "kind", v, True)),
                choice_box(starts, fit.after, lambda v, f=fit: self._set_fit(f, "after", v, True)),
                start,
                length,
                remove_button(lambda _=False, f=fit: self._remove(p.fits, f), fit.name),
            )
        self.checklist.set_chosen(p.kinetic_measures)
        names = [pulse.name for pulse in p.pulses]
        self.pulses.show_pulses(names, names if p.kinetic_pulses is None else p.kinetic_pulses)
        self.smoothing.blockSignals(True)
        self.smoothing.setValue(p.kinetic_smoothing_frames)
        self.smoothing.blockSignals(False)

    def add_fit(self):
        first = self.protocol.pulses[0].name if self.protocol.pulses else None
        name = self.protocol.new_name("Tau ") if any(f.name == "Tau" for f in self.protocol.fits) else "Tau"
        self.protocol.fits.append(Fit(name, first, 4 if first else 0, round(2000 / self.protocol.sampling_interval_ms)))
        self.changed.emit(True)

    def _set_fit(self, fit, attribute, value, rebuild=False):
        setattr(fit, attribute, value)
        self.changed.emit(rebuild)

    def _remove(self, items, item):
        items.remove(item)
        self.changed.emit(True)

    def _set_measures(self):
        self.protocol.kinetic_measures = self.checklist.chosen()
        self.changed.emit(False)

    def _set_pulses(self):
        chosen = self.pulses.chosen()
        self.protocol.kinetic_pulses = None if len(chosen) == len(self.protocol.pulses) else chosen
        self.changed.emit(False)

    def _set_smoothing(self, value):
        self.protocol.kinetic_smoothing_frames = value
        self.changed.emit(False)


# ---------------------------------------------------------------------------
# 4. Spatial
# ---------------------------------------------------------------------------


class SpatialEditor(Editor):
    def __init__(self, units):
        super().__init__(units)
        self.pulses = PulseChoice(self._set_pulses)
        self.checklist = Checklist(SPATIAL, self._set_measures)
        self.box("Spread over the slice", QLabel("Measured on the response maps of:"), self.pulses, self.checklist,
                 explanation="Each chosen pulse gets a response map: the response of every pixel, averaged over a few "
                             "frames around the peak of the ROI trace. It is measured in rings around the ROI centre. "
                             "The plot on the right shows the map and its rings while this tab is open.")
        self.near_to_far = PulseChoice(self._set_near_to_far)
        self.box("Near-to-far index", self.near_to_far,
                 explanation="For each ticked comparison (see the Comparisons tab), the same comparison measured on the "
                             "response maps in the far band, divided by the same in the near band.")

        self.inputs = {}
        settings = QWidget()
        grid = QGridLayout(settings)
        grid.setContentsMargins(0, 0, 0, 0)
        for row, f in enumerate(fields(SpatialSettings)):
            details = f.metadata
            if details["kind"] == "bool":
                widget = QCheckBox()
                widget.toggled.connect(self._set_settings)
            else:
                widget = QSpinBox() if details["kind"] == "int" else QDoubleSpinBox()
                widget.setRange(details["minimum"], details["maximum"])
                widget.setSingleStep(details["step"])
                if details["kind"] != "int":
                    widget.setDecimals(1)
                widget.setSuffix(f" {details['unit']}")
                widget.setKeyboardTracking(False)
                widget.valueChanged.connect(self._set_settings)
            label = QLabel(details["label"] + ":")
            for item in (label, widget):
                item.setToolTip(details["help"])
            grid.addWidget(label, row // 2, 2 * (row % 2))
            grid.addWidget(widget, row // 2, 2 * (row % 2) + 1)
            self.inputs[f.name] = widget
        self.box("Maps and rings", settings, explanation="Hover over a setting for what it does. The defaults suit the 4× objective.")
        self.content.addStretch()

    def fill(self):
        p = self.protocol
        self.pulses.show_pulses([pulse.name for pulse in p.pulses], p.spatial_pulses)
        self.checklist.set_chosen(p.spatial_measures)
        self.near_to_far.show_pulses([c.name for c in p.comparisons], p.near_to_far)
        for f in fields(SpatialSettings):
            widget, value = self.inputs[f.name], getattr(p.spatial, f.name)
            widget.blockSignals(True)
            if isinstance(widget, QCheckBox):
                widget.setChecked(value)
            else:
                widget.setValue(value)
            widget.blockSignals(False)

    def _set_pulses(self):
        self.protocol.spatial_pulses = self.pulses.chosen()
        self.changed.emit(False)

    def _set_measures(self):
        self.protocol.spatial_measures = self.checklist.chosen()
        self.changed.emit(False)

    def _set_near_to_far(self):
        self.protocol.near_to_far = self.near_to_far.chosen()
        self.changed.emit(False)

    def _set_settings(self):
        for f in fields(SpatialSettings):
            widget = self.inputs[f.name]
            value = widget.isChecked() if isinstance(widget, QCheckBox) else widget.value()
            setattr(self.protocol.spatial, f.name, value)
        self.changed.emit(False)


# ---------------------------------------------------------------------------
# 5. Comparisons and summary
# ---------------------------------------------------------------------------


class ComparisonsEditor(Editor):
    def __init__(self, units):
        super().__init__(units)
        self.comparisons = Rows(["Name", "Response of", "", "Divided by", "As", ""])
        add_comparison = QPushButton("Add comparison")
        add_comparison.clicked.connect(self.add_comparison)
        normalise = QPushButton("Add every pulse relative to the first")
        normalise.setToolTip("Adds the response of every pulse divided by the response of the first pulse.")
        normalise.clicked.connect(self.add_normalised)
        self.box("Comparisons", self.comparisons, row_of(add_comparison, normalise),
                 explanation="The response of one pulse divided by the response of another, e.g. P2 ÷ P1, the paired-pulse ratio.")

        self.statistics = {name: check_box(False, lambda on, n=name: self._set_statistic(n, on), name) for name in STATISTICS}
        self.in_range = check_box(False, self._set_range_on, "Mean over recordings with a condition from")
        self.low, self.high = QDoubleSpinBox(), QDoubleSpinBox()
        for box in (self.low, self.high):
            box.setRange(-1e6, 1e6)
            box.setDecimals(1)
            box.setKeyboardTracking(False)
            box.valueChanged.connect(self._set_range)
        self.spread = check_box(False, self._set_spread, "Baseline spread: how much each baseline varies between the recordings")
        self.box("Slice summary", row_of("Over the recordings of a slice:", *self.statistics.values()),
                 row_of(self.in_range, self.low, "to", self.high), self.spread,
                 explanation="One value per slice (per recording folder), combining its recordings, e.g. the mean dF/F "
                             "over 100 to 400 µA. Every measure of the other tabs is summarised.")

        self.condition_fits = Rows(["Name", "Measure", "Curve", "Plateau", ""])
        add_fit = QPushButton("Add fit across conditions")
        add_fit.clicked.connect(self.add_condition_fit)
        self.box("Fits across conditions", self.condition_fits, row_of(add_fit),
                 explanation="A curve fitted per slice to one measure against the condition of its recordings. "
                             "Recovery: plateau − (plateau − start)·exp(−x/τ), e.g. P11/P1 against the delay, with the "
                             "plateau fixed at 100 % for full recovery. Saturation: top·xⁿ ÷ (halfⁿ + xⁿ), e.g. the "
                             "response against the current, which gives the half-max current.")
        self.content.addStretch()

    def fill(self):
        p = self.protocol
        pulses = [(pulse.name, pulse.name) for pulse in p.pulses]
        self.comparisons.clear()
        for comparison in p.comparisons:
            self.comparisons.add(
                name_box(comparison.name, lambda new, old=comparison.name: self.rename(old, new)),
                choice_box(pulses, comparison.pulse, lambda v, c=comparison: self._set_comparison(c, "pulse", v)),
                QLabel("÷"),
                choice_box(pulses, comparison.relative_to, lambda v, c=comparison: self._set_comparison(c, "relative_to", v)),
                choice_box([("ratio", RATIO_SCALE), ("percent", PERCENT_SCALE)], comparison.scale,
                           lambda v, c=comparison: self._set_comparison(c, "scale", v)),
                remove_button(lambda _=False, c=comparison: self._remove(c), comparison.name),
            )
        self._fill_condition_fits()
        widgets = [*self.statistics.values(), self.in_range, self.low, self.high, self.spread]
        for widget in widgets:
            widget.blockSignals(True)
        for name, box in self.statistics.items():
            box.setChecked(name in p.summary_statistics)
        self.in_range.setChecked(p.summary_condition_range is not None)
        low, high = p.summary_condition_range or (100, 400)
        for box, value in ((self.low, low), (self.high, high)):
            box.setSuffix(f" {p.condition_unit}" if p.condition_unit else "")
            box.setValue(value)
        self.low.setEnabled(self.in_range.isChecked())
        self.high.setEnabled(self.in_range.isChecked())
        self.spread.setChecked(p.summary_baseline_spread)
        for widget in widgets:
            widget.blockSignals(False)

    def _set_comparison(self, comparison, attribute, value):
        automatic = comparison.name == f"{comparison.pulse}/{comparison.relative_to}"
        setattr(comparison, attribute, value)
        if automatic and attribute != "scale":
            new = self._free(f"{comparison.pulse}/{comparison.relative_to}", comparison)
            self.protocol.rename(comparison.name, new)
        self.changed.emit(True)

    def _free(self, name, owner=None):
        """`name`, or `name 2`, `name 3`… if another window, pulse, comparison or fit already uses it."""
        taken = set(self.protocol.names()) - ({owner.name} if owner is not None else set())
        candidate, number = name, 2
        while candidate in taken:
            candidate, number = f"{name} {number}", number + 1
        return candidate

    def add_comparison(self):
        pulses = [p.name for p in self.protocol.pulses]
        if not pulses:
            return
        pulse, relative_to = pulses[min(1, len(pulses) - 1)], pulses[0]
        self.protocol.comparisons.append(Comparison(self._free(f"{pulse}/{relative_to}"), pulse, relative_to))
        self.changed.emit(True)

    def add_normalised(self):
        pulses = [p.name for p in self.protocol.pulses]
        if not pulses:
            return
        existing = {(c.pulse, c.relative_to, c.scale) for c in self.protocol.comparisons}
        for pulse in pulses:
            if (pulse, pulses[0], RATIO_SCALE) not in existing:
                self.protocol.comparisons.append(Comparison(self._free(f"n{pulse}/BL"), pulse, pulses[0], RATIO_SCALE))
        self.changed.emit(True)

    def _remove(self, comparison):
        self.protocol.comparisons.remove(comparison)
        self.protocol.near_to_far = [n for n in self.protocol.near_to_far if n != comparison.name]
        self.changed.emit(True)

    def _set_statistic(self, name, on):
        chosen = self.protocol.summary_statistics
        self.protocol.summary_statistics = [s for s in STATISTICS if (s == name and on) or (s != name and s in chosen)]
        self.changed.emit(True)

    def _set_range_on(self, on):
        self.protocol.summary_condition_range = [self.low.value(), self.high.value()] if on else None
        self.low.setEnabled(on)
        self.high.setEnabled(on)
        self.changed.emit(True)

    def _set_range(self):
        if self.protocol.summary_condition_range is not None:
            self.protocol.summary_condition_range = [self.low.value(), self.high.value()]
            self.changed.emit(True)

    def _set_spread(self, on):
        self.protocol.summary_baseline_spread = on
        self.changed.emit(True)

    def _fill_condition_fits(self):
        p = self.protocol
        measures = [(m.name, m.name) for m in p.measures() if m.per == "recording"]
        units = {m.name: m.unit for m in p.measures()}
        models = [("recovery", RECOVERY), ("saturation (input–output)", SATURATION)]
        self.condition_fits.clear()
        for fit in p.condition_fits:
            if fit.model == RECOVERY:
                fixed = check_box(fit.plateau is not None, lambda on, f=fit: self._set_plateau_fixed(f, on), "fixed at")
                value = QDoubleSpinBox()
                value.setRange(-1e6, 1e6)
                value.setDecimals(2)
                value.setKeyboardTracking(False)
                value.setSuffix(f" {units.get(fit.measure)}" if units.get(fit.measure) not in (None, "", "ratio") else "")
                value.setValue(_full_recovery(units.get(fit.measure)) if fit.plateau is None else fit.plateau)
                value.setEnabled(fit.plateau is not None)
                value.valueChanged.connect(lambda v, f=fit: self._set_plateau(f, v))
                plateau = row_of(fixed, value)
            else:
                plateau = QLabel("–")
            self.condition_fits.add(
                name_box(fit.name, lambda new, old=fit.name: self.rename(old, new)),
                choice_box(measures, fit.measure, lambda v, f=fit: self._set_fit(f, "measure", v)),
                choice_box(models, fit.model, lambda v, f=fit: self._set_fit(f, "model", v)),
                plateau,
                remove_button(lambda _=False, f=fit: self._remove_condition_fit(f), fit.name),
            )

    def _set_fit(self, fit, attribute, value):
        setattr(fit, attribute, value)
        self.changed.emit(True)

    def _set_plateau_fixed(self, fit, on):
        units = {m.name: m.unit for m in self.protocol.measures()}
        fit.plateau = _full_recovery(units.get(fit.measure)) if on else None
        self.changed.emit(True)

    def _set_plateau(self, fit, value):
        if fit.plateau is not None:
            fit.plateau = value
            self.changed.emit(False)

    def add_condition_fit(self):
        """A recovery fit of the recovery pulse relative to the first, when there is a pulse set per recording;
        an input–output fit of the first pulse's response otherwise."""
        p = self.protocol
        if not p.pulses:
            return
        recovered = set(p.per_recording_pulses())
        first = p.pulses[0].name
        comparison = next((c for c in p.comparisons if c.pulse in recovered and c.relative_to == first), None)
        if comparison is not None:
            plateau = _full_recovery("%" if comparison.scale == PERCENT_SCALE else "ratio")
            fit = ConditionFit(self._free("Recovery"), comparison.name, RECOVERY, plateau)
        else:
            fit = ConditionFit(self._free("Input-output"), f"{first} response", SATURATION)
        p.condition_fits.append(fit)
        self.changed.emit(True)

    def _remove_condition_fit(self, fit):
        self.protocol.condition_fits.remove(fit)
        self.changed.emit(True)


def _full_recovery(unit):
    """The plateau of a full recovery: 1 for a ratio, 100 for a percentage."""
    return 1.0 if unit == "ratio" else 100.0
