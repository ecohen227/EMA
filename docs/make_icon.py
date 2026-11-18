"""Draws EMA's icon files from its drawings.

    python docs/make_icon.py

ema/assets/ema.svg is the logo; ema/assets/ema_small.svg is the same logo with thicker lines, for 32 pixels and
less, where thin lines blur away. This writes ema/assets/ema.png (256 × 256, the window icon and the splash screen)
and ema/assets/ema.ico (16 to 256 pixels, the icon of the desktop shortcut), each size drawn from the drawing rather
than shrunk from a picture, so that every line stays sharp.
"""

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt  # noqa: E402
from PyQt5.QtGui import QImage, QPainter  # noqa: E402
from PyQt5.QtSvg import QSvgRenderer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "ema" / "assets"
SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
SMALL = 32  # this size and less are drawn from ema_small.svg


def render(drawing, size):
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(str(drawing)).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def png_bytes(image):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def write_ico(path, images):
    """An .ico file holding one PNG per size (as Windows Vista and later read them)."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        side = 0 if size >= 256 else size  # 0 stands for 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    Path(path).write_bytes(header + entries + blobs)


def main():
    app = QApplication(sys.argv)  # Qt needs one to draw
    images = [(size, png_bytes(render(ASSETS / ("ema_small.svg" if size <= SMALL else "ema.svg"), size)))
              for size in SIZES]
    (ASSETS / "ema.png").write_bytes(dict(images)[256])
    write_ico(ASSETS / "ema.ico", images)
    print("wrote", ASSETS / "ema.png", "and", ASSETS / "ema.ico", f"({', '.join(map(str, SIZES))} px)")
    app.quit()


if __name__ == "__main__":
    main()
