"""The strip of small cards under the plots: every recording of a folder at a glance.

Each card shows the response map of one recording with the ROI on it, the
trace of the ROI and the peak of that trace. All cards share one colour
scale and one trace scale, so they can be compared directly.
"""

import numpy as np
from matplotlib import colormaps
from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QHBoxLayout, QScrollArea, QWidget

MAP_SIZE = 80  # side of the response map on a card
TRACE_HEIGHT = 30
MARGIN, TEXT_HEIGHT = 6, 16
CARD_WIDTH = MAP_SIZE + 2 * MARGIN
CARD_HEIGHT = MAP_SIZE + TRACE_HEIGHT + 2 * TEXT_HEIGHT + 2 * MARGIN
FLAG = "⚑"
FLAG_COLOR, SELECTED_COLOR, TRACE_COLOR = QColor("#d1242f"), QColor("#0969da"), QColor("#1f4e79")


class RecordingCard(QWidget):
    """One recording: title, response map with the ROI, ROI trace, peak."""

    def __init__(self, strip, key, title):
        super().__init__()
        self.strip, self.key, self.title = strip, key, title
        self.response = None  # response map (dF/F, %)
        self.trace = None  # ROI trace (dF/F, %)
        self.picture = None  # the response map as a coloured picture
        self.caption = "loading…"
        self.selected = self.flagged = False
        self.set_apart = False  # drawn greyed, for a card that is not an ordinary recording
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.strip.selected.emit(self.key)
        elif event.button() == Qt.RightButton:
            self.strip.flag_toggled.emit(self.key)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().midlight() if self.set_apart else self.palette().base())
        map_area = QRectF(MARGIN, MARGIN + TEXT_HEIGHT, MAP_SIZE, MAP_SIZE)
        trace_area = QRectF(MARGIN, map_area.bottom() + 2, MAP_SIZE, TRACE_HEIGHT)

        painter.setPen(FLAG_COLOR if self.flagged else self.palette().text().color())
        title = f"{FLAG} {self.title}" if self.flagged else self.title
        title = painter.fontMetrics().elidedText(title, Qt.ElideRight, MAP_SIZE)
        painter.drawText(QRectF(MARGIN, MARGIN, MAP_SIZE, TEXT_HEIGHT), Qt.AlignCenter, title)
        painter.setPen(self.palette().text().color())
        painter.drawText(QRectF(MARGIN, trace_area.bottom(), MAP_SIZE, TEXT_HEIGHT), Qt.AlignCenter, self.caption)

        if self.picture is not None:
            painter.drawPixmap(map_area, self.picture, QRectF(self.picture.rect()))
            self._draw_roi(painter, map_area)
            self._draw_trace(painter, trace_area)

        if self.flagged or self.selected:
            painter.setPen(QPen(FLAG_COLOR if self.flagged else SELECTED_COLOR, 3))
            painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

    def _draw_roi(self, painter, area):
        if self.strip.roi is None:
            return
        (x, y), radius = self.strip.roi
        scale = MAP_SIZE / self.response.shape[1]
        painter.setClipRect(area)
        painter.setPen(QPen(Qt.white, 1.5))
        painter.drawEllipse(area.topLeft() + QPointF(x + 0.5, y + 0.5) * scale, radius * scale, radius * scale)
        painter.setClipping(False)

    def _draw_trace(self, painter, area):
        low, high = self.strip.trace_limits
        across = area.left() + np.linspace(0, area.width(), len(self.trace))
        down = area.bottom() - (self.trace - low) / max(high - low, 1e-9) * area.height()
        painter.setPen(QPen(TRACE_COLOR, 1))
        painter.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(across, down)]))


class RecordingStrip(QScrollArea):
    """A row of cards. A left click on a card selects it, a right click asks to flag it."""

    selected = pyqtSignal(str)
    flag_toggled = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cards = {}  # key -> RecordingCard
        self.roi = None  # (centre, radius), drawn on every card
        self.trace_limits = (0, 1)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(CARD_HEIGHT + self.horizontalScrollBar().sizeHint().height() + 6)

    def show_cards(self, titles, apart=None):
        """Start a new row of empty cards. `titles` maps the key of each card to its title.

        The card with the key `apart` is greyed and followed by a gap, to show it is not an ordinary recording.
        """
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)
        self.cards = {key: RecordingCard(self, key, title) for key, title in titles.items()}
        for key, card in self.cards.items():
            layout.addWidget(card)
            if key == apart:
                card.set_apart = True
                layout.addSpacing(12)
        layout.addStretch()
        self.setWidget(row)

    def fill(self, key, response, trace, caption):
        """Give a card its response map (dF/F, %), ROI trace (dF/F, %) and caption."""
        card = self.cards[key]
        card.response, card.trace, card.caption = response, trace, caption
        self._rescale()

    def fail(self, key, caption, reason):
        """Say on a card that its recording could not be shown."""
        card = self.cards[key]
        card.response = card.trace = card.picture = None
        card.caption = caption
        card.setToolTip(reason)
        card.update()

    def _rescale(self):
        """Give all filled cards the same colour scale and the same trace scale."""
        filled = [card for card in self.cards.values() if card.response is not None]
        brightest = max(np.percentile(card.response, 99.9) for card in filled)
        self.trace_limits = min(card.trace.min() for card in filled), max(card.trace.max() for card in filled)
        for card in filled:
            card.picture = picture_of(card.response, 0, brightest)
            card.update()

    def show_roi(self, center, radius):
        self.roi = (center, radius)
        for card in self.cards.values():
            card.update()

    def select(self, key):
        for card in self.cards.values():
            card.selected = card.key == key
            card.update()
        self.ensureWidgetVisible(self.cards[key])

    def show_flags(self, flagged_keys):
        for card in self.cards.values():
            card.flagged = card.key in flagged_keys
            card.update()


def picture_of(image, low, high, colormap="inferno"):
    """A 2D array as a coloured picture; `low` maps to the darkest colour and `high` to the brightest."""
    colors = colormaps[colormap]((image - low) / max(high - low, 1e-9), bytes=True)
    colors = np.ascontiguousarray(colors)
    rows, columns = image.shape
    picture = QImage(colors.data, columns, rows, 4 * columns, QImage.Format_RGBA8888)
    return QPixmap.fromImage(picture.copy())
