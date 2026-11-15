"""Small widgets the configurator's editors are built from."""

from PyQt5.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QWidget,
)

MAX_FRAME = 100_000


class Units:
    """How times are shown: in frames or in ms. Times are always stored in frames."""

    def __init__(self):
        self.in_ms = False
        self.frame_ms = 4.849

    @property
    def name(self):
        return "ms" if self.in_ms else "frames"


class FrameBox(QDoubleSpinBox):
    """A time stored in frames and shown in frames or in ms. With `optional`, the lowest value means none."""

    edited = pyqtSignal()

    def __init__(self, units, frames, optional=False):
        super().__init__()
        self.units, self.optional = units, optional
        scale = units.frame_ms if units.in_ms else 1
        self.setDecimals(1 if units.in_ms else 0)
        self.setSingleStep(scale)
        self.setRange(-scale if optional else 0, MAX_FRAME * scale)
        if optional:
            self.setSpecialValueText("none")
        self.setKeyboardTracking(False)  # report a typed number when it is complete, not every digit
        self.setValue(-scale if frames is None else frames * scale)
        self.setToolTip(f"In {units.name}. Stored as a whole number of frames ({units.frame_ms:g} ms each).")
        self.valueChanged.connect(self.edited)

    def frames(self):
        if self.optional and self.value() < 0:
            return None
        return round(self.value() / self.units.frame_ms) if self.units.in_ms else round(self.value())


def name_box(text, on_finished):
    box = QLineEdit(text)
    box.setMinimumWidth(70)
    box.editingFinished.connect(lambda: on_finished(box.text().strip()))
    return box


def choice_box(choices, current, on_chosen):
    """A drop-down list of (label, value) pairs."""
    box = QComboBox()
    for label, value in choices:
        box.addItem(label, value)
    index = box.findData(current)
    box.setCurrentIndex(max(index, 0))
    box.activated.connect(lambda i: on_chosen(box.itemData(i)))
    return box


def check_box(checked, on_toggled, text=""):
    box = QCheckBox(text)
    box.setChecked(checked)
    box.toggled.connect(on_toggled)
    return box


def remove_button(on_clicked, what):
    button = QPushButton("✕")
    button.setFixedWidth(28)
    button.setToolTip(f"Remove {what}")
    button.clicked.connect(on_clicked)
    return button


def hint(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray")
    return label


class SideScroll(QScrollArea):
    """Holds a wide widget, such as a table: scrolls sideways when the tab is narrower, and is always as tall as
    the widget, so the text around it keeps the width of the tab."""

    def __init__(self, widget):
        super().__init__()
        self.setWidget(widget)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.widget():
            if event.type() == QEvent.LayoutRequest:
                self.updateGeometry()  # rows were added or removed: follow the new height
            elif event.type() in (QEvent.HideToParent, QEvent.ShowToParent):
                self.setVisible(event.type() == QEvent.ShowToParent)  # the table was hidden or shown on purpose
        return False

    def sizeHint(self):
        hint = self.widget().sizeHint()
        return QSize(hint.width(), hint.height() + self.horizontalScrollBar().sizeHint().height())

    def minimumSizeHint(self):
        return QSize(80, self.sizeHint().height())


class Rows(QWidget):
    """A small table: a row of headings, then one row of widgets per item. Rebuilt whole when items change."""

    def __init__(self, headings):
        super().__init__()
        self.headings = headings
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.rows = 0
        self.clear()

    def clear(self, headings=None):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)  # off the screen now, not only once Qt deletes it
                widget.deleteLater()
        self.headings = headings or self.headings
        for column, heading in enumerate(self.headings):
            label = QLabel("<b>" + heading.replace("\n", "<br>") + "</b>")
            label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
            self.grid.addWidget(label, 0, column)
        self.rows = 0

    def add(self, *widgets):
        """Add a row. A None after a widget makes that widget span the next column too."""
        self.rows += 1
        placed = []  # [widget, first column, number of columns]
        for column, widget in enumerate(widgets):
            if widget is None and placed:
                placed[-1][2] += 1
            elif widget is not None:
                placed.append([widget, column, 1])
        for widget, column, span in placed:
            self.grid.addWidget(widget, self.rows, column, 1, span, Qt.AlignVCenter)


def row_of(*widgets, stretch=True):
    """Widgets side by side, as one widget."""
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(QLabel(widget) if isinstance(widget, str) else widget)
    if stretch:
        layout.addStretch()
    return holder
