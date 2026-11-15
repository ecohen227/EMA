"""'Place pulses…': make the pulses and windows of a regular train from how it was stimulated."""

from PyQt5.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from .widgets import FrameBox, hint


class PlacePulsesDialog(QDialog):
    def __init__(self, protocol, units, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Place pulses")
        self.frame_ms = protocol.sampling_interval_ms
        fixed = [p for p in protocol.pulses if not p.per_recording and p.peak is not None]
        first = fixed[0] if fixed else None
        stimuli = [p.stimulus for p in fixed if p.stimulus is not None]
        shared = len({p.baseline for p in fixed}) == 1 and len(fixed) > 1
        baseline = protocol.baseline_window(first.baseline) if first else None

        self.first = FrameBox(units, stimuli[0] if stimuli else 103)
        self.count = QSpinBox()
        self.count.setRange(1, 500)
        self.count.setValue(max(len(fixed), 1))
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.1, 1e6)
        self.interval.setDecimals(3)
        self.interval.setSuffix(" ms")
        # The mean interval over the whole train: stimuli are whole frames, so neighbours differ by ±1 frame
        self.interval.setValue((stimuli[-1] - stimuli[0]) / (len(stimuli) - 1) * self.frame_ms if len(stimuli) >= 2 else 100.0)
        self.peak_length = FrameBox(units, first.peak.end - first.peak.start if first else 20)
        self.baseline_length = FrameBox(units, baseline.end - baseline.start if baseline else 15)
        self.shared = QRadioButton("One baseline before the first pulse, shared by all (BL)")
        self.each = QRadioButton("A baseline right before each pulse (B1, B2, …)")
        group = QButtonGroup(self)
        group.addButton(self.shared)
        group.addButton(self.each)
        (self.shared if shared else self.each).setChecked(True)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        for box in (self.first, self.peak_length, self.baseline_length):
            box.edited.connect(self.show_summary)
        self.count.valueChanged.connect(self.show_summary)
        self.interval.valueChanged.connect(self.show_summary)

        form = QFormLayout()
        form.addRow(f"First stimulus at ({units.name}):", self.first)
        form.addRow("Number of pulses:", self.count)
        form.addRow("Time between pulses:", self.interval)
        form.addRow(f"Peak window length ({units.name}):", self.peak_length)
        form.addRow(f"Baseline window length ({units.name}):", self.baseline_length)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Place pulses")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        self.setMinimumWidth(520)
        layout.addWidget(hint("Each peak window starts at its stimulus; each baseline window ends at the stimulus it belongs to. "
                              "This replaces the pulses and baselines of the protocol, except those set per recording."))
        layout.addLayout(form)
        layout.addWidget(self.shared)
        layout.addWidget(self.each)
        layout.addWidget(self.summary)
        layout.addWidget(buttons)
        self.show_summary()
        self.resize(self.minimumWidth(), self.heightForWidth(self.minimumWidth()))

    def values(self):
        """The arguments of Protocol.place_pulses."""
        return (self.first.frames(), self.count.value(), self.interval.value() / self.frame_ms,
                self.peak_length.frames(), self.baseline_length.frames(), self.shared.isChecked())

    def show_summary(self):
        first, count, interval, *_ = self.values()
        stimuli = [round(first + k * interval) for k in range(count)]
        shown = ", ".join(str(s) for s in stimuli[:6]) + (", …" if count > 6 else ".")
        frequency = 1000 / self.interval.value()
        self.summary.setText(f"{count} pulse(s) at {frequency:.3g} Hz, stimulated at frames {shown}")
