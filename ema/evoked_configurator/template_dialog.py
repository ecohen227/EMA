"""New…: the template form that every protocol, 2P and 11P included, can be built from."""

from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from ..evoked.protocol import AS_LISTED, BRIGHTNESS, NO_PARTNER, RATIO, RECORDED_AFTER
from ..evoked.template import END_OF_TRAIN, LAST_PULSE, LIKE, Template
from ..recordings import FRAME_MS
from .widgets import hint, row_of


def ms_box(value, maximum=1e6):
    box = QDoubleSpinBox()
    box.setRange(0.1, maximum)
    box.setDecimals(1)
    box.setSuffix(" ms")
    box.setValue(value)
    return box


class TemplateDialog(QDialog):
    """Asks for the few numbers a protocol is built from. `template()` gives them back."""

    def __init__(self, parent=None, name="New protocol", frame_ms=FRAME_MS):
        super().__init__(parent)
        self.setWindowTitle("New protocol")
        self.setMinimumWidth(900)
        self.name = QLineEdit(name)
        self.frame_ms = QDoubleSpinBox()
        self.frame_ms.setRange(0.001, 10000)
        self.frame_ms.setDecimals(3)
        self.frame_ms.setSuffix(" ms")
        self.frame_ms.setValue(frame_ms)

        self.brightness = QRadioButton("Brightness of the ROI (dF/F)")
        self.ratio = QRadioButton("Stimulated ÷ unstimulated, in %")
        traces = QButtonGroup(self)
        for button in (self.brightness, self.ratio):
            traces.addButton(button)
        self.brightness.setChecked(True)
        self.partner_after = QRadioButton("The unstimulated recording made right after it")
        self.partner_after.setToolTip("Found from the time stamps the camera stores in the files.")
        self.partner_listed = QRadioButton("The one named in the list of recordings")
        self.partner_none = QRadioButton("None: brightness as recorded, without correcting for bleaching")
        partners = QButtonGroup(self)
        for button in (self.partner_after, self.partner_listed, self.partner_none):
            partners.addButton(button)
        self.partner_after.setChecked(True)

        self.first = QSpinBox()
        self.first.setRange(0, 1_000_000)
        self.first.setSuffix(" (frame)")
        self.count = QSpinBox()
        self.count.setRange(1, 500)
        self.interval, self.peak, self.baseline = ms_box(4000), ms_box(600), ms_box(60)
        self.shared = QRadioButton("One baseline before the first pulse, shared by all")
        self.own = QRadioButton("A baseline right before each pulse")
        baselines = QButtonGroup(self)
        baselines.addButton(self.shared)
        baselines.addButton(self.own)
        self.own.setChecked(True)

        self.recovery = QCheckBox("Add a recovery pulse (a different delay in each recording)")
        self.delays = QLineEdit("500, 1000, 2500, 5000")
        self.delays.setToolTip("Delays in ms, separated by commas: one recording each.")
        self.after = QComboBox()
        self.after.addItems([END_OF_TRAIN, LAST_PULSE])
        self.after.setToolTip("The end of the train is one interval after its last pulse.")
        self.stimulated, self.unstimulated = QLineEdit("hi{n}.tif"), QLineEdit("no{n+1}.tif")
        self.stimulated.setToolTip("{n} stands for the recording's number: 1, 2, 3 …")
        self.unstimulated.setToolTip("{n+1} stands for the number after the stimulated recording's: the unstimulated "
                                     "recording made right after it.")
        self.summary = QLabel()
        self.summary.setWordWrap(True)

        like = [QPushButton(f"Fill in like {name}") for name in LIKE]
        for button, name in zip(like, LIKE):
            button.clicked.connect(lambda _=False, n=name: self.show_template(LIKE[n]))

        pulses = QFormLayout()
        pulses.addRow("First stimulus at:", self.first)
        pulses.addRow("Number of pulses:", self.count)
        pulses.addRow("Time between pulses:", self.interval)
        pulses.addRow("Peak window, from each stimulus:", self.peak)
        pulses.addRow("Baseline window, ending at its stimulus:", self.baseline)
        pulse_box = QGroupBox("The train of pulses")
        pulse_layout = QVBoxLayout(pulse_box)
        pulse_layout.addLayout(pulses)
        pulse_layout.addWidget(self.own)
        pulse_layout.addWidget(self.shared)

        recovery = QFormLayout()
        recovery.addRow("Delays:", self.delays)
        recovery.addRow("Counted from:", self.after)
        recovery.addRow("Stimulated files (n = 1, 2 …):", self.stimulated)
        recovery.addRow("Unstimulated partners:", self.unstimulated)
        recovery_box = QGroupBox("Recovery pulse")
        recovery_layout = QVBoxLayout(recovery_box)
        recovery_layout.addWidget(self.recovery)
        recovery_layout.addLayout(recovery)

        about = QFormLayout()
        about.addRow("Name:", self.name)
        about.addRow("Time between frames:", self.frame_ms)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Create")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hint("Every protocol is built from the same template: a train of pulses and, if you want, a "
                              "recovery pulse. The built-in 2P and 11P are two fillings of it. Everything can be "
                              "fine-tuned afterwards, on the plot or in the tabs."))
        layout.addWidget(row_of(*like))
        layout.addLayout(about)
        trace_box = QGroupBox("Trace that is measured")
        trace_layout = QVBoxLayout(trace_box)
        trace_layout.addWidget(self.brightness)
        trace_layout.addWidget(self.ratio)
        trace_layout.addWidget(QLabel("Unstimulated partner of each stimulated recording:"))
        for button in (self.partner_after, self.partner_listed, self.partner_none):
            trace_layout.addWidget(button)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.addWidget(trace_box)
        left.addWidget(pulse_box)
        right.addWidget(recovery_box)
        right.addStretch()
        columns = QHBoxLayout()
        columns.addLayout(left)
        columns.addLayout(right)
        layout.addLayout(columns)
        layout.addWidget(self.summary)
        layout.addWidget(buttons)

        for widget in (self.first, self.count):
            widget.valueChanged.connect(self.show_summary)
        for widget in (self.interval, self.peak, self.baseline, self.frame_ms):
            widget.valueChanged.connect(self.show_summary)
        for widget in (self.brightness, self.recovery, self.shared, self.partner_after, self.partner_listed):
            widget.toggled.connect(self.show_summary)
        self.delays.textChanged.connect(self.show_summary)
        self.after.currentIndexChanged.connect(self.show_summary)
        self.show_template(Template(name=name, frame_ms=frame_ms))
        self.resize(self.minimumWidth(), self.heightForWidth(self.minimumWidth()))

    def show_template(self, template):
        keep_name = self.name.text()
        self.frame_ms.setValue(template.frame_ms)
        (self.brightness if template.trace == BRIGHTNESS else self.ratio).setChecked(True)
        {RECORDED_AFTER: self.partner_after, AS_LISTED: self.partner_listed, NO_PARTNER: self.partner_none}[template.partner].setChecked(True)
        self.first.setValue(template.first_stimulus)
        self.count.setValue(template.pulses)
        self.interval.setValue(template.interval_ms)
        self.peak.setValue(template.peak_ms)
        self.baseline.setValue(template.baseline_ms)
        (self.shared if template.shared_baseline else self.own).setChecked(True)
        self.recovery.setChecked(template.recovery)
        self.delays.setText(", ".join(f"{d:g}" for d in template.recovery_delays_ms))
        self.after.setCurrentText(template.recovery_after)
        self.stimulated.setText(template.stimulated_files)
        self.unstimulated.setText(template.unstimulated_files)
        self.name.setText(keep_name)
        self.show_summary()

    def delays_ms(self):
        try:
            return [float(text) for text in self.delays.text().split(",") if text.strip()]
        except ValueError:
            return None

    def template(self):
        return Template(
            name=self.name.text().strip(),
            frame_ms=self.frame_ms.value(),
            trace=BRIGHTNESS if self.brightness.isChecked() else RATIO,
            partner=self.partner(),
            first_stimulus=self.first.value(),
            pulses=self.count.value(),
            interval_ms=self.interval.value(),
            peak_ms=self.peak.value(),
            baseline_ms=self.baseline.value(),
            shared_baseline=self.shared.isChecked(),
            recovery=self.recovery.isChecked(),
            recovery_delays_ms=self.delays_ms() or [],
            recovery_after=self.after.currentText(),
            stimulated_files=self.stimulated.text().strip(),
            unstimulated_files=self.unstimulated.text().strip(),
        )

    def partner(self):
        if self.partner_listed.isChecked():
            return AS_LISTED
        return NO_PARTNER if self.partner_none.isChecked() else RECORDED_AFTER

    def show_summary(self):
        if self.ratio.isChecked() and self.partner_none.isChecked():
            self.partner_after.setChecked(True)  # a ratio needs a partner
        self.partner_none.setEnabled(self.brightness.isChecked())
        for widget in (self.delays, self.after):
            widget.setEnabled(self.recovery.isChecked())
        self.stimulated.setEnabled(self.recovery.isChecked() or self.partner_listed.isChecked())
        self.unstimulated.setEnabled(self.partner_listed.isChecked())
        template = self.template()
        stimuli = template.stimuli()
        shown = ", ".join(str(s) for s in stimuli[:6]) + (", …" if len(stimuli) > 6 else "")
        text = f"{template.pulses} pulse(s) at {1000 / template.interval_ms:.3g} Hz, stimulated at frames {shown}."
        if template.recovery:
            if self.delays_ms() is None:
                text += "  ⚠ The delays must be numbers separated by commas."
            else:
                recovery = ", ".join(f"{template.recovery_stimulus(d)} ({d:g} ms)" for d in template.recovery_delays_ms)
                text += f" Recovery pulse at frames {recovery}."
        if self.stimulated.isEnabled():
            files = [template.file_name(template.stimulated_files, n) for n in (1, 2)]
            if self.unstimulated.isEnabled():
                files = [f"{f} ÷ {template.file_name(template.unstimulated_files, n)}" for n, f in zip((1, 2), files)]
            text += f" Recordings: {', '.join(files)}, …"
        self.summary.setText(text)

    def accept(self):
        if not self.name.text().strip():
            QMessageBox.information(self, "New protocol", "Give the protocol a name.")
        elif self.recovery.isChecked() and not self.delays_ms():
            QMessageBox.information(self, "New protocol", "Give the delays of the recovery pulse, in ms, separated by commas.")
        else:
            super().accept()
