"""Takes the screenshots of the documentation from the real program.

    python docs/make_screenshots.py [folder with the sample recordings]

The windows are drawn off screen, so nothing appears on the desktop. The
screenshots are saved in docs/screenshots.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ["QT_SCALE_FACTOR"] = "1.5"

from matplotlib.backend_bases import MouseEvent
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

app = QApplication([])
app.setFont(QFont("Segoe UI", 9))

from ema import user_settings
from ema.launcher import Launcher
from ema.roi_selection import Selections
from ema.roi_selection.setup_dialog import SetupDialog
from ema.roi_selection.window import VIEW_BASELINE, VIEW_RESPONSE, RoiSelectionWindow

DOCS = Path(__file__).parent
SCREENSHOTS = DOCS / "screenshots"
HANDOFF = DOCS.parents[1] / "EMA_V3_handoff_2026-11-14" / "EMA_V3_handoff_2026-11-14"
SAMPLE_DATA = HANDOFF / "4_sample_data" / "recordings"


def save(widget, name):
    app.processEvents()
    widget.grab().save(str(SCREENSHOTS / name))
    print("saved", name)


def mouse(view, kind, x, y, button=1):
    """Send a mouse event at image position (x, y)."""
    px, py = view.axes.transData.transform((x, y))
    view.callbacks.process(kind, MouseEvent(kind, view, px, py, button))


def main():
    recordings = (Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE_DATA).resolve()
    SCREENSHOTS.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp())
    user_settings.FILE = output / "settings.json"  # leave the real remembered folders alone

    launcher = Launcher()
    launcher.show()
    save(launcher, "launcher.png")

    dialog = SetupDialog()
    dialog.recordings.path.setText(str(recordings))
    dialog.recordings.changed.emit()
    dialog.preview.folder_box.setCurrentIndex(1)
    dialog.recordings.path.setText("C:/Users/you/Recordings")
    dialog.output.path.setText("C:/Users/you/EMA results")
    dialog.filter.skip_with.setText("4ap, wash")
    dialog.show()
    save(dialog, "setup.png")
    dialog.preview.view_box.setCurrentIndex(1)
    dialog.form.inputs["electrode_threshold"].setValue(0.97)
    dialog.show_example()
    save(dialog, "setup_example.png")

    window = RoiSelectionWindow(Selections(recordings), output)
    window.resize(1300, 740)
    window.show()
    window.detect_all()
    window.folder_list.setCurrentRow(1)
    window.finish_strip()
    save(window, "window.png")

    x, y = window.selection.roi_center
    window.move_roi(x + 14, y - 12)
    window.drop_roi()
    window.finish_strip()
    save(window, "move_roi.png")
    window.use_automatic_roi()
    window.finish_strip()

    window.view_box.setCurrentText(VIEW_BASELINE)
    window.electrode_tool.setChecked(True)
    app.processEvents()
    window.image.draw()
    outline = [(40, 55), (55, 52), (72, 60), (78, 70), (70, 80), (52, 84), (40, 80)]
    mouse(window.image, "button_press_event", *outline[0])
    for point in outline[1:]:
        mouse(window.image, "motion_notify_event", *point)
    save(window, "edit_electrode_drawing.png")
    mouse(window.image, "button_release_event", *outline[-1])
    save(window, "edit_electrode_done.png")
    window.use_automatic_electrode()
    window.roi_tool.setChecked(True)

    window.view_box.setCurrentText(VIEW_RESPONSE)
    window.toggle_flag("no6.tif")
    window.reason.setText("example of a flag")
    window.flag_recording(True)
    window.slider.setValue(window.peak + 40)
    save(window, "flag_and_slider.png")
    window.accept_and_next()
    save(window, "reviewed.png")


if __name__ == "__main__":
    main()
