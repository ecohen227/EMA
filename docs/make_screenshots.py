"""Takes the screenshots of the documentation from the real program.

    python docs/make_screenshots.py [folder with the sample recordings]

The windows are drawn off screen, so nothing appears on the desktop. The
screenshots are saved in docs/screenshots.
"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ["QT_SCALE_FACTOR"] = "1.5"

import numpy as np
import tifffile
from matplotlib.backend_bases import MouseEvent
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

app = QApplication([])
app.setFont(QFont("Segoe UI", 9))

from ema import user_settings
from ema.evoked.metrics import KINETIC_KEYS, SPATIAL_KEYS
from ema.evoked.template import LIKE
from ema.evoked_analysis.window import AnalysisWindow
from ema.evoked_configurator.pulse_dialog import PlacePulsesDialog
from ema.evoked_configurator.template_dialog import TemplateDialog
from ema.evoked_configurator.window import ConfiguratorWindow
from ema.launcher import Launcher
from ema.roi_selection import FolderSelection, RoiSettings, Selections
from ema.roi_selection.setup_dialog import SetupDialog
from ema.roi_selection.window import VIEW_BASELINE, VIEW_RESPONSE, RoiSelectionWindow

DOCS = Path(__file__).parent
SCREENSHOTS = DOCS / "screenshots"
HANDOFF = DOCS.parents[1] / "EMA_V3_handoff_2026-11-14" / "EMA_V3_handoff_2026-11-14"
SAMPLE_DATA = HANDOFF / "4_sample_data" / "recordings"


def save(widget, name):
    app.processEvents()
    app.processEvents()  # tables that scroll sideways take a second pass to reach their height
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
    dialog.form.sections["Electrode"].heading.click()
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
    configurator_screenshots(recordings, output)
    analysis_screenshots(output)


def configurator_screenshots(recordings, output):
    window = ConfiguratorWindow(user_folder=output / "protocols")
    window.resize(1450, 820)
    window.use_example_folder(recordings / "2P_input_output", None)
    window.show()
    save(window, "configurator.png")

    window.protocol.kinetic_measures = list(KINETIC_KEYS)
    window.protocol.spatial_measures = list(SPATIAL_KEYS)
    window.protocol.near_to_far = ["PPR"]
    window.protocol_changed(True)
    window.tabs.setCurrentIndex(2)
    save(window, "configurator_kinetics.png")
    window.tabs.setCurrentIndex(3)
    save(window, "configurator_spatial.png")
    window.spatial_view.view_box.setCurrentText("Decay with distance")
    save(window, "configurator_decay.png")
    window.spatial_view.view_box.setCurrentIndex(0)
    window.tabs.setCurrentIndex(0)

    template = TemplateDialog(window)
    template.show_template(LIKE["11P pulse train"])
    template.name.setText("My 10 Hz train")
    template.show()
    save(template, "configurator_template.png")
    template.close()

    window.open_entry(2)
    window.use_example_folder(recordings / "11P_at_200uA", None)
    window.tabs.setCurrentIndex(0)
    save(window, "configurator_recordings.png")
    window.tabs.setCurrentIndex(1)
    window.plot.axes.set_xlim(60, 460)
    window.plot.draw()
    save(window, "configurator_pulses.png")

    dialog = PlacePulsesDialog(window.protocol, window.units, window)
    dialog.show()
    save(dialog, "configurator_place_pulses.png")
    dialog.close()

    window.editors[4].add_condition_fit()
    window.tabs.setCurrentIndex(4)
    app.processEvents()
    bar = window.editors[4].verticalScrollBar()
    bar.setValue(bar.maximum())  # down to the fits across conditions
    save(window, "configurator_summary.png")
    window.saved = window.protocol.to_dict()
    window.close()


DEMO_FOLDERS = [
    "Females/LKI HET F5819/CTRL 2HR/Slice 1/input output",
    "Females/LKI HET F5819/IFNy 2HR/Slice 2/input output",
    "Females/LKI HET F5774/IFN 4HR/slice4/input output",
    "Males/LKI WT M5820/CTRL 2HR/Slice 1/input output",
    "Males/LKI WT M5820/IFN 2H/Slice 3/input output",
    "Males/LKI WT M5770/Contrl 4HR/Slice 2/input output",
]


def demo_movie(path, response, clock, seed):
    """A small movie with two responses at the 2P stimulus frames, for the window screenshots."""
    rng = np.random.default_rng(seed)
    frames = np.arange(1301) - 1
    course = sum(np.where(frames >= s, size * np.exp(-(frames - s) / 35.0), 0.0) for s, size in ((103, 1.0), (928, 0.6)))
    y, x = np.indices((32, 32))
    spot = np.exp(-((x - 16) ** 2 + (y - 16) ** 2) / 50.0)
    movie = 500 * (1 + response * course[:, None, None] * spot) * np.exp(-frames / 20000)[:, None, None]
    movie += rng.normal(0, 6, movie.shape)
    stamp = datetime.strptime(f"2025:12:05 {clock}", "%Y:%m:%d %H:%M:%S")
    tifffile.imwrite(path, movie.clip(0).astype(np.uint16), datetime=stamp)


def demo_study(root):
    """Six recording folders named like the lab's, with their ROI file. Nothing real is read or written."""
    settings = RoiSettings()
    selections = Selections(root, settings)
    for n, name in enumerate(DEMO_FOLDERS):
        folder = root / name
        folder.mkdir(parents=True)
        for k, (file, response) in enumerate((("100uA.tif", 0.15), ("no1.tif", 0), ("200uA.tif", 0.3), ("no2.tif", 0),
                                              ("300uA.tif", 0.4), ("no3.tif", 0))):
            demo_movie(folder / file, response * (1 + 0.15 * n), f"10:0{k}:00", 10 * n + k)
        selections.folders[name] = FolderSelection((32, 32), (16, 16), settings.roi_radius_px, np.zeros((32, 32), bool),
                                                   reviewed=True)
    selections.save(root.parent / "roi_selections.json")
    return root.parent / "roi_selections.json"


def analysis_screenshots(output):
    roi_file = demo_study(output / "demo" / "recordings")
    window = AnalysisWindow(user_folder=output / "protocols")
    window.resize(1400, 820)
    window.roi_input.path.setText(str(roi_file))
    window.load_roi_file()
    window.output.path.setText(str(output / "demo" / "Evoked 2P"))
    window.output_changed()
    window.roi_input.path.setText("C:/Users/you/EMA results/roi_selections.json")
    window.output.path.setText("C:/Users/you/EMA results/Evoked 2P")
    window.roi_info.setText("Recordings folder: C:/Users/you/Recordings\n6 folders with an ROI, 6 of them reviewed.")
    window.filter.only_with.setText("input output")
    window.show()
    save(window, "analysis.png")
    window.tabs.setCurrentIndex(2)
    save(window, "analysis_near_misses.png")
    window.near_misses.apply(window.near_misses.misses[0], ("Treatment", "CTRL"))
    window.tabs.setCurrentIndex(1)
    window.labels_editor.tree.setCurrentItem(window.labels_editor.tree.topLevelItem(2).child(0))
    save(window, "analysis_labels.png")
    window.tabs.setCurrentIndex(0)
    window.output.path.setText(str(output / "demo" / "Evoked 2P"))
    window.start()
    window.worker.wait()
    app.processEvents()
    window.output.path.setText("C:/Users/you/EMA results/Evoked 2P")
    save(window, "analysis_done.png")
    window.close()


if __name__ == "__main__":
    main()
