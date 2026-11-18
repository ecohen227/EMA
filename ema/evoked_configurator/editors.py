"""The three tabs of the configurator: recordings, pulses and windows, and measures.

Each tab shows part of the protocol and changes it in place. It then emits
`changed(True)` when names or the number of things changed, so that every
tab is filled again, and `changed(False)` when only a value changed.
"""

import re

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..evoked.protocol import (
    AS_LISTED,
    BRIGHTNESS,
    EVERY,
    LISTED,
    NO_PARTNER,
    PER_RECORDING,
    RATIO,
    RECORDED_AFTER,
    PulseTiming,
    Recording,
    Window,
)
from .pulse_dialog import PlacePulsesDialog
from .widgets import FrameBox, Rows, SideScroll, check_box, choice_box, hint, name_box, remove_button, row_of


class Editor(QScrollArea):
    """A tab that shows part of a protocol and changes it in place."""

    changed = pyqtSignal(bool)  # True when every tab must be filled again

    def __init__(self, units):
        super().__init__()
        self.units = units
        self.protocol = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        self.content = QVBoxLayout(holder)
        self.content.setSizeConstraint(QLayout.SetMinimumSize)  # scroll rather than squeeze long lists
        self.setWidget(holder)

    def show_protocol(self, protocol):
        self.protocol = protocol
        self.fill()

    def fill(self):
        raise NotImplementedError

    def box(self, title, *widgets, explanation=""):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        if explanation:
            layout.addWidget(hint(explanation))
        for widget in widgets:
            layout.addWidget(SideScroll(widget) if isinstance(widget, Rows) else widget)  # wide tables scroll sideways
        self.content.addWidget(group)
        return group

    def rename(self, old, new):
        """Rename a baseline, pulse, comparison or fit. False (and a message) if the name cannot be used."""
        if new == old:
            return False
        if not new or new in self.protocol.names():
            QMessageBox.information(self, "Name", f"'{new}' cannot be used: every name must be different and not empty.")
            self.changed.emit(True)  # puts the old name back
            return False
        self.protocol.rename(old, new)
        self.changed.emit(True)
        return True


# ---------------------------------------------------------------------------
# 1. Recordings
# ---------------------------------------------------------------------------


class RecordingsEditor(Editor):
    def __init__(self, units):
        super().__init__(units)
        self.name = QLineEdit()
        self.name.editingFinished.connect(lambda: self._set("name", self.name.text().strip()))
        self.description = QLineEdit()
        self.description.setPlaceholderText("What the protocol is for (optional)")
        self.description.editingFinished.connect(lambda: self._set("description", self.description.text().strip()))
        self.interval = QDoubleSpinBox()
        self.interval.setDecimals(3)
        self.interval.setRange(0.001, 10000)
        self.interval.setSuffix(" ms")
        self.interval.setKeyboardTracking(False)
        self.interval.valueChanged.connect(self._set_interval)
        about = QWidget()
        form = QFormLayout(about)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Name:", self.name)
        form.addRow("Description:", self.description)
        form.addRow("Time between frames:", self.interval)
        self.box("Protocol", about)

        self.brightness = QRadioButton("Brightness of the ROI")
        self.ratio = QRadioButton("Stimulated ÷ unstimulated, in %")
        traces = QButtonGroup(self)
        traces.addButton(self.brightness)
        traces.addButton(self.ratio)
        self.brightness.toggled.connect(self._set_trace)
        self.box(
            "Trace that is measured",
            self.brightness,
            _indented(hint("The brightness of the ROI, corrected for bleaching when it has an unstimulated partner (below). "
                           "A response is the change of brightness from its baseline, in percent (dF/F).")),
            self.ratio,
            _indented(hint("Each stimulated recording divided by its unstimulated partner, − 1, in %. "
                           "A response is the rise above its baseline, in percentage points.")),
        )

        self.after = QRadioButton("The unstimulated recording made right after it")
        self.as_listed = QRadioButton("The one named in the list of recordings")
        self.no_partner = QRadioButton("None: measure the brightness as recorded")
        partners = QButtonGroup(self)
        for button in (self.after, self.as_listed, self.no_partner):
            partners.addButton(button)
            button.toggled.connect(self._set_partner)
        self.as_listed.setToolTip("Needs a list of recordings (below).")
        self.correction_note = hint("")
        self.box(
            "Unstimulated partner",
            self.after,
            _indented(hint("Found from the time stamps in the files; if none was made after it, the one made right before it. "
                           "Unstimulated recordings are the ones whose name starts with 'no' and a number, such as no6.tif. "
                           "A listed recording can name another partner.")),
            self.as_listed,
            self.no_partner,
            _indented(hint("For slices recorded without unstimulated recordings. Bleaching is then not corrected.")),
            self.correction_note,
        )

        self.every = QRadioButton("Every stimulated recording in the folder (all but the ones whose name starts with 'no')")
        self.listed = QRadioButton("Only these recordings:")
        selections = QButtonGroup(self)
        selections.addButton(self.every)
        selections.addButton(self.listed)
        self.every.toggled.connect(self._set_selection)
        self.skip_words = QLineEdit()
        self.skip_words.setToolTip("Recordings with one of these words in their name are not measured, e.g. 'hi1 red.tif'.")
        self.skip_words.editingFinished.connect(self._set_skip_words)
        self.condition_name, self.condition_unit = QLineEdit(), QLineEdit()
        self.condition_name.setMaximumWidth(140)
        self.condition_unit.setMaximumWidth(70)
        self.condition_name.editingFinished.connect(lambda: self._set("condition_name", self.condition_name.text().strip()))
        self.condition_unit.editingFinished.connect(lambda: self._set("condition_unit", self.condition_unit.text().strip()))
        self.condition_note = hint("")
        self.follow = check_box(False, self._set_follow, "Per-recording windows follow the condition")
        self.follow_note = _indented(hint("Changing a recording's delay (in ms) moves its own windows by as much."))
        self.rows = Rows([])
        self.add_button = QPushButton("Add recording")
        self.add_button.clicked.connect(self.add_recording)
        self.every_part = row_of("Skip recordings with these words:", self.skip_words, stretch=False)
        self.box(
            "Recordings that are measured",
            self.every,
            self.every_part,
            self.listed,
            self.rows,
            row_of(self.add_button),
            row_of("Each recording's condition:", self.condition_name, "in", self.condition_unit),
            self.condition_note,
            self.follow,
            self.follow_note,
        )
        self.content.addStretch()

    def fill(self):
        p = self.protocol
        widgets = (self.name, self.description, self.interval, self.brightness, self.ratio, self.every, self.listed,
                   self.after, self.as_listed, self.no_partner)
        for widget in widgets:
            widget.blockSignals(True)
        self.name.setText(p.name)
        self.description.setText(p.description)
        self.description.setCursorPosition(0)  # show the start of a long description
        self.description.setToolTip(p.description)
        self.interval.setValue(p.sampling_interval_ms)
        self.brightness.setChecked(p.trace == BRIGHTNESS)
        self.ratio.setChecked(p.trace == RATIO)
        self.every.setChecked(p.selection == EVERY)
        self.listed.setChecked(p.selection == LISTED)
        self.after.setChecked(p.partner == RECORDED_AFTER)
        self.as_listed.setChecked(p.partner == AS_LISTED)
        self.no_partner.setChecked(p.partner == NO_PARTNER)
        for widget in widgets:
            widget.blockSignals(False)
        self.as_listed.setEnabled(p.selection == LISTED)
        self.no_partner.setEnabled(p.trace == BRIGHTNESS)
        self.correction_note.setText(
            "The bleaching is divided out frame by frame: stimulated × (mean of the partner over the first baseline "
            "window) ÷ partner. The trace stays in brightness units, so dF/F keeps its meaning."
            if p.trace == BRIGHTNESS and p.partner != NO_PARTNER else ""
        )
        self.correction_note.setVisible(bool(self.correction_note.text()))
        self.skip_words.setText(", ".join(p.skip_words))
        self.condition_name.setText(p.condition_name)
        self.condition_unit.setText(p.condition_unit)
        self.every_part.setVisible(p.selection == EVERY)
        self.rows.setVisible(p.selection == LISTED)
        self.add_button.setVisible(p.selection == LISTED)
        self.follow.blockSignals(True)
        self.follow.setChecked(p.windows_follow_condition)
        self.follow.blockSignals(False)
        self.follow.setVisible(p.selection == LISTED and bool(p.per_recording_baselines() or p.per_recording_pulses()))
        self.follow_note.setVisible(self.follow.isVisibleTo(self))
        self.condition_note.setText(
            "Taken from the first number in each file name, e.g. 200 for 200uA.tif."
            if p.selection == EVERY
            else "Typed for each recording above. Used to tell the recordings of a slice apart and in slice summaries."
        )
        self._fill_rows()

    def _fill_rows(self):
        p = self.protocol
        condition = p.condition_name or "Condition"
        if p.condition_unit:
            condition += f"\n({p.condition_unit})"
        headings = ["File"] + (["Unstimulated"] if p.uses_partner else []) + [condition]
        for name in p.per_recording_baselines():
            headings += [f"{name}\nfrom", "\nup to"]
        for name in p.per_recording_pulses():
            headings += [f"{name}\nstimulus", f"{name}\nfrom", "\nup to"]
        self.rows.clear(headings + [""])
        for recording in p.recordings:
            widgets = [name_box(recording.file, lambda text, r=recording: self._set_file(r, "file", text))]
            if p.uses_partner:
                partner = name_box(recording.unstimulated, lambda text, r=recording: self._set_file(r, "unstimulated", text))
                if p.partner == RECORDED_AFTER:
                    partner.setPlaceholderText("made after it")
                    partner.setToolTip("Leave empty for the unstimulated recording made right after it, or name another.")
                widgets.append(partner)
            condition_box = QLineEdit("" if recording.condition is None else f"{recording.condition:g}")
            condition_box.setMaximumWidth(80)
            condition_box.editingFinished.connect(lambda r=recording, b=condition_box: self._set_condition(r, b))
            widgets.append(condition_box)
            for name in p.per_recording_baselines():
                window = recording.baselines.get(name) or Window(0, 10)
                widgets += self._window_boxes(window, lambda w, r=recording, n=name: r.baselines.__setitem__(n, w))
            for name in p.per_recording_pulses():
                timing = recording.pulses.setdefault(name, PulseTiming())
                stimulus = FrameBox(self.units, timing.stimulus, optional=True)
                stimulus.edited.connect(lambda t=timing, b=stimulus: self._set_stimulus(t, b))
                widgets.append(stimulus)
                widgets += self._window_boxes(timing.peak or Window(0, 10), lambda w, t=timing: setattr(t, "peak", w))
            widgets.append(remove_button(lambda _=False, r=recording: self._remove(r), recording.file))
            self.rows.add(*widgets)

    def _window_boxes(self, window, store):
        start, end = FrameBox(self.units, window.start), FrameBox(self.units, window.end)

        def edited():
            store(Window(start.frames(), end.frames()))
            self.changed.emit(False)

        start.edited.connect(edited)
        end.edited.connect(edited)
        return [start, end]

    def _set_stimulus(self, timing, box):
        timing.stimulus = box.frames()
        self.changed.emit(False)

    def _set(self, attribute, value):
        if getattr(self.protocol, attribute) != value:
            setattr(self.protocol, attribute, value)
            self.changed.emit(attribute.startswith("condition"))

    def _set_interval(self, value):
        self.protocol.sampling_interval_ms = value
        self.units.frame_ms = value
        self.changed.emit(True)

    def _set_trace(self):
        self.protocol.trace = BRIGHTNESS if self.brightness.isChecked() else RATIO
        if self.protocol.trace == RATIO and self.protocol.partner == NO_PARTNER:
            self.protocol.partner = RECORDED_AFTER  # a ratio needs a partner
        self.changed.emit(True)

    def _set_partner(self, checked):
        if not checked:
            return
        self.protocol.partner = RECORDED_AFTER if self.after.isChecked() else AS_LISTED if self.as_listed.isChecked() else NO_PARTNER
        self.changed.emit(True)

    def _set_selection(self):
        p = self.protocol
        p.selection = EVERY if self.every.isChecked() else LISTED
        if p.selection == EVERY and p.partner == AS_LISTED:
            p.partner = RECORDED_AFTER  # partners can only be named in a list
        if p.selection == EVERY:  # only listed recordings can have timing of their own
            for name in p.per_recording_baselines():
                p.set_baseline_per_recording(name, False)
            for pulse in p.pulses:
                p.set_pulse_per_recording(pulse, False)
        self.changed.emit(True)

    def _set_skip_words(self):
        words = [word.strip() for word in self.skip_words.text().split(",") if word.strip()]
        if words != self.protocol.skip_words:
            self.protocol.skip_words = words
            self.changed.emit(True)

    def _set_file(self, recording, attribute, text):
        if getattr(recording, attribute) != text:
            setattr(recording, attribute, text)
            self.changed.emit(True)

    def _set_condition(self, recording, box):
        try:
            value = float(box.text()) if box.text().strip() else None
        except ValueError:
            box.setText("" if recording.condition is None else f"{recording.condition:g}")
            return
        self.protocol.set_condition(recording, value)
        self.changed.emit(self.protocol.windows_follow_condition)  # the windows in the row may have moved

    def _set_follow(self, on):
        self.protocol.windows_follow_condition = on
        self.changed.emit(False)

    def add_recording(self):
        p = self.protocol
        if p.recordings:
            last = p.recordings[-1]
            recording = Recording(_next_name(last.file), _next_name(last.unstimulated), last.condition,
                                  {n: Window(w.start, w.end) for n, w in last.baselines.items()},
                                  {n: PulseTiming(t.stimulus, t.peak and Window(t.peak.start, t.peak.end)) for n, t in last.pulses.items()})
        else:
            recording = Recording("hi1.tif", "no2.tif" if p.partner == AS_LISTED else "")
            for name in p.per_recording_baselines():
                recording.baselines[name] = Window(0, 10)
            for name in p.per_recording_pulses():
                recording.pulses[name] = PulseTiming(None, Window(10, 30))
        p.recordings.append(recording)
        self.changed.emit(True)

    def _remove(self, recording):
        self.protocol.recordings.remove(recording)
        self.changed.emit(True)


def _next_name(name):
    """'hi1.tif' -> 'hi2.tif': the last number in a file name, plus one."""
    numbers = list(re.finditer(r"\d+", name))
    if not numbers:
        return name
    last = numbers[-1]
    return name[: last.start()] + str(int(last.group()) + 1) + name[last.end():]


def _indented(widget):
    widget.setContentsMargins(22, 0, 0, 4)
    return widget


# ---------------------------------------------------------------------------
# 2. Pulses and windows
# ---------------------------------------------------------------------------


class PulsesEditor(Editor):
    def __init__(self, units):
        super().__init__(units)
        self.in_frames, self.in_ms = QRadioButton("frames"), QRadioButton("ms")
        unit_group = QButtonGroup(self)
        unit_group.addButton(self.in_frames)
        unit_group.addButton(self.in_ms)
        self.in_ms.toggled.connect(self._set_units)
        place = QPushButton("Place pulses…")
        place.setToolTip("Make the pulses and windows of a regular train from its first stimulus, number of pulses and interval.")
        place.clicked.connect(self.place_pulses)
        self.box(
            "Timing",
            row_of("Show times in:", self.in_frames, self.in_ms),
            row_of(place, hint("Builds every window from the stimulation; fine-tune them below or by dragging them on the plot.")),
            explanation="Frame 0 is the second frame of the recording, because the first is dropped when it is read.",
        )
        self.baselines = Rows(["Baseline", "From", "Up to", "Per\nrecording", ""])
        add_baseline = QPushButton("Add baseline")
        add_baseline.clicked.connect(self.add_baseline)
        self.box("Baseline windows", self.baselines, row_of(add_baseline),
                 explanation="The mean of the trace over a baseline window is the level a pulse is measured from. Several pulses may share one baseline.")
        self.pulses = Rows(["Pulse", "Stimulus", "Peak\nfrom", "\nup to", "Baseline", "Per\nrecording", ""])
        add_pulse = QPushButton("Add pulse")
        add_pulse.clicked.connect(self.add_pulse)
        self.write_peaks = check_box(False, self._set_write_peaks, "Write the peak of each pulse too (P1 peak, …)")
        self.write_peaks.setToolTip("The response of each pulse (its dF/F) is always written. Tick this to also write "
                                    "its peak: the maximum of the trace over the peak window, in the unit of the trace.")
        self.box("Pulses", self.pulses, row_of(add_pulse), self.write_peaks,
                 explanation="The maximum of the trace over a peak window is the peak of the pulse. The stimulus is only used "
                             "for the response shape (time to peak, area). 'Per recording' gives a pulse its own timing in each "
                             "listed recording, e.g. a recovery pulse after different delays.")
        self.content.addStretch()

    def fill(self):
        p = self.protocol
        for button in (self.in_frames, self.in_ms):
            button.blockSignals(True)
        self.in_ms.setChecked(self.units.in_ms)
        self.in_frames.setChecked(not self.units.in_ms)
        for button in (self.in_frames, self.in_ms):
            button.blockSignals(False)
        self.write_peaks.blockSignals(True)
        self.write_peaks.setChecked(p.write_peaks)
        self.write_peaks.blockSignals(False)
        listed = p.selection == LISTED
        per_recording_tip = "" if listed else "Only possible when only listed recordings are measured (Recordings tab)."

        self.baselines.clear()
        for name, window in p.baselines.items():
            per = window == PER_RECORDING
            boxes = [_per_recording_label(), None] if per else self._window_boxes(lambda w, n=name: p.baselines.__setitem__(n, w), window)
            toggle = check_box(per, lambda on, n=name: self._per_recording_baseline(n, on))
            toggle.setEnabled(listed)
            toggle.setToolTip(per_recording_tip)
            self.baselines.add(name_box(name, lambda new, old=name: self.rename(old, new)), *boxes, toggle,
                               remove_button(lambda _=False, n=name: self._remove_baseline(n), name))

        self.pulses.clear()
        baseline_choices = [(name, name) for name in p.baselines]
        for pulse in p.pulses:
            if pulse.per_recording:
                timing = [_per_recording_label(), None, None]
            else:
                stimulus = FrameBox(self.units, pulse.stimulus, optional=True)
                stimulus.edited.connect(lambda pl=pulse, b=stimulus: self._set_stimulus(pl, b))
                timing = [stimulus] + self._window_boxes(lambda w, pl=pulse: setattr(pl, "peak", w), pulse.peak or Window(0, 10))
            baseline = choice_box(baseline_choices, pulse.baseline, lambda value, pl=pulse: self._set_baseline(pl, value))
            toggle = check_box(pulse.per_recording, lambda on, pl=pulse: self._per_recording_pulse(pl, on))
            toggle.setEnabled(listed)
            toggle.setToolTip(per_recording_tip)
            self.pulses.add(name_box(pulse.name, lambda new, old=pulse.name: self.rename(old, new)), *timing, baseline, toggle,
                            remove_button(lambda _=False, pl=pulse: self._remove_pulse(pl), pulse.name))

    def _set_write_peaks(self, on):
        self.protocol.write_peaks = on
        self.changed.emit(True)

    def _window_boxes(self, store, window):
        start, end = FrameBox(self.units, window.start), FrameBox(self.units, window.end)

        def edited():
            store(Window(start.frames(), end.frames()))
            self.changed.emit(False)

        start.edited.connect(edited)
        end.edited.connect(edited)
        return [start, end]

    def _set_units(self, in_ms):
        self.units.in_ms = in_ms
        self.changed.emit(True)

    def _set_stimulus(self, pulse, box):
        pulse.stimulus = box.frames()
        self.changed.emit(False)

    def _set_baseline(self, pulse, name):
        pulse.baseline = name
        self.changed.emit(False)

    def _per_recording_baseline(self, name, on):
        self.protocol.set_baseline_per_recording(name, on)
        self.changed.emit(True)

    def _per_recording_pulse(self, pulse, on):
        self.protocol.set_pulse_per_recording(pulse, on)
        self.changed.emit(True)

    def add_baseline(self):
        self.protocol.add_baseline()
        self.changed.emit(True)

    def add_pulse(self):
        self.protocol.add_pulse()
        self.changed.emit(True)

    def _remove_baseline(self, name):
        users = [pulse.name for pulse in self.protocol.pulses if pulse.baseline == name]
        if users:
            QMessageBox.information(self, "Baseline in use", f"{name} is the baseline of {', '.join(users)}. Choose another baseline for them first.")
            return
        del self.protocol.baselines[name]
        for recording in self.protocol.recordings:
            recording.baselines.pop(name, None)
        self.changed.emit(True)

    def _remove_pulse(self, pulse):
        self.protocol.pulses.remove(pulse)
        for recording in self.protocol.recordings:
            recording.pulses.pop(pulse.name, None)
        self.changed.emit(True)

    def place_pulses(self):
        dialog = PlacePulsesDialog(self.protocol, self.units, self)
        if dialog.exec_():
            self.protocol.place_pulses(*dialog.values())
            self.changed.emit(True)


def _per_recording_label():
    label = QLabel("set per recording")
    label.setStyleSheet("color: gray")
    label.setToolTip("Set for each listed recording on the Recordings tab, or by dragging it on the plot.")
    return label
