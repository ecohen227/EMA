"""Takes the screenshots of the documentation from the real program.

    python docs/make_screenshots.py [folder with the sample recordings]

The windows are drawn off screen, so nothing appears on the desktop. The
screenshots are saved in docs/screenshots.
"""

import os
import shutil
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
from ema.evoked.catalogue import KINETIC_KEYS, SPATIAL_KEYS
from ema.evoked.template import LIKE
from ema.evoked.workbook import PER_RECORDING, PER_SLICE
from ema.evoked_analysis.window import EvokedAnalysisWindow
from ema.spontaneous.workbook import PER_EVENT
from ema.spontaneous.workbook import PER_SLICE as SPONTANEOUS_PER_SLICE
from ema.spontaneous_analysis.window import SpontaneousAnalysisWindow
from ema.spontaneous_configurator.window import SpontaneousConfiguratorWindow
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
    spontaneous_screenshots(recordings, output)
    spontaneous_analysis_screenshots(recordings, output)


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

    window.bar.open(2)
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
    window.bar.saved = window.protocol.to_dict()
    window.close()


def shown_as(field, text):
    """Show a tidy path in a file or folder input without the window reading it (it is made up)."""
    field.set_path(text)


# The made-up study of the Evoked Analysis screenshots and example tables: two slices per group, one folder
# misspelt ('Contrl'). Each entry: folder, size of the response, paired-pulse ratio.
DEMO_FOLDERS = [
    ("Males/LKI WT M5820/CTRL 2HR/Slice 1/input output", 1.0, 0.55),
    ("Males/LKI WT M5770/Contrl 2HR/Slice 2/input output", 0.85, 0.6),
    ("Males/LKI WT M5820/IFN 2H/Slice 3/input output", 1.3, 0.45),
    ("Males/LKI WT M5770/IFNy 2HR/Slice 1/input output", 1.15, 0.4),
    ("Females/LKI HET F5819/CTRL 2HR/Slice 1/input output", 0.6, 0.6),
    ("Females/LKI HET F5774/CTRL 2HR/slice3/input output", 0.7, 0.65),
    ("Females/LKI HET F5819/IFNy 2HR/Slice 2/input output", 0.8, 0.5),
    ("Females/LKI HET F5774/IFN 2H/Slice 4/input output", 0.9, 0.45),
]
DEMO_CURRENTS = [50, 100, 200, 300, 400]
EXAMPLES = DOCS / "examples"


def demo_movie(path, response, ppr, clock, seed):
    """A small movie with two responses at the 2P stimulus frames."""
    rng = np.random.default_rng(seed)
    frames = np.arange(1301) - 1
    course = sum(np.where(frames >= s, size * np.exp(-(frames - s) / 60.0), 0.0) for s, size in ((103, 1.0), (928, ppr)))
    y, x = np.indices((32, 32))
    spot = np.exp(-((x - 16) ** 2 + (y - 16) ** 2) / 50.0)
    movie = 500 * (1 + response * course[:, None, None] * spot) * np.exp(-frames / 20000)[:, None, None]
    movie += rng.normal(0, 6, movie.shape)
    stamp = datetime.strptime(f"2025:12:05 {clock}", "%Y:%m:%d %H:%M:%S")
    tifffile.imwrite(path, movie.clip(0).astype(np.uint16), datetime=stamp)


def demo_study(root):
    """Eight recording folders named like the lab's, with their ROI file. Nothing real is read or written."""
    settings = RoiSettings()
    selections = Selections(root, settings)
    rng = np.random.default_rng(1)
    for n, (name, size, ppr) in enumerate(DEMO_FOLDERS):
        folder = root / name
        folder.mkdir(parents=True)
        for k, current in enumerate(DEMO_CURRENTS):
            response = 5.0 * size * current**1.5 / (150**1.5 + current**1.5) * rng.uniform(0.9, 1.1)
            demo_movie(folder / f"{current}uA.tif", response, ppr * rng.uniform(0.85, 1.15), f"10:{2 * k:02d}:00", 20 * n + k)
            demo_movie(folder / f"no{k + 1}.tif", 0.0, 0.0, f"10:{2 * k + 1:02d}:00", 20 * n + 10 + k)
        selections.folders[name] = FolderSelection((32, 32), (16, 16), settings.roi_radius_px, np.zeros((32, 32), bool),
                                                   reviewed=True)
    selections.save(root.parent / "roi_selections.json")
    return root.parent / "roi_selections.json"


def analysis_screenshots(output):
    """The Evoked Analysis window at each step, and the two Excel files of the demo study as examples."""
    roi_file = demo_study(output / "demo" / "recordings")
    window = EvokedAnalysisWindow(user_folder=output / "protocols")
    window.resize(1400, 760)
    window.roi_input.path.setText(str(roi_file))
    window.load_roi_file()
    window.output.path.setText(str(output / "demo" / "Evoked 2P"))
    window.output_changed()
    shown_as(window.roi_input, "C:/Users/you/EMA results/roi_selections.json")
    shown_as(window.output, "C:/Users/you/EMA results/Evoked 2P")
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
    shown_as(window.output, str(output / "demo" / "Evoked 2P"))
    window.start()
    window.worker.wait()
    app.processEvents()
    shown_as(window.output, "C:/Users/you/EMA results/Evoked 2P")
    save(window, "analysis_done.png")
    window.close()
    EXAMPLES.mkdir(exist_ok=True)
    for name in (PER_RECORDING, PER_SLICE):
        shutil.copyfile(output / "demo" / "Evoked 2P" / name, EXAMPLES / ("Example - " + name))
        print("saved Example -", name)


def spontaneous_screenshots(recordings, output):
    """The Spontaneous Event Configurator on the sample unstimulated recording with two events planted in it."""
    from make_spontaneous_figures import planted_example

    root = output / "spontaneous"
    folder = root / "Slice 1" / "input output"
    center, electrode = planted_example(recordings, folder)
    selections = Selections(root, RoiSettings())
    selections.folders[selections.name_of(folder)] = FolderSelection(electrode.shape, center, RoiSettings().roi_radius_px,
                                                                     electrode, reviewed=True)
    selections.save(root / "roi_selections.json")
    window = SpontaneousConfiguratorWindow(user_folder=output / "detectors")
    window.resize(1450, 820)
    window.use_example_folder(folder, root / "roi_selections.json")
    window.worker.wait()
    app.processEvents()
    window.folder_label.setText("C:/Users/you/Recordings/…/Slice 1/input output")
    window.form.sections["Spatial filter"].heading.click()
    window.show()
    save(window, "spontaneous_configurator.png")
    window.bar.saved = window.detector.to_dict()
    window.close()


SPONTANEOUS_FOLDERS = [  # folder, events per recording (two recordings), peak dF/F scale
    ("Males/LKI WT M5820/CTRL 2HR/Slice 1/input output", (2, 1), 1.0),
    ("Males/LKI WT M5820/IFN 2H/Slice 3/input output", (3, 2), 1.2),
    ("Females/LKI HET F5819/CTRL 2HR/Slice 1/input output", (1, 1), 0.8),
    ("Females/LKI HET F5819/IFNy 2HR/Slice 2/input output", (2, 2), 0.9),
]


def spontaneous_analysis_screenshots(recordings, output):
    """The Spontaneous Event Analysis on four made-up slices: copies of the sample's unstimulated recording with planted
    events (1 to 3 per recording, 2–5 % peak, σ 96–176 µm); the two Excel files are kept as examples."""
    from make_spontaneous_figures import planted_example

    root = output / "spontaneous_demo" / "recordings"
    rng = np.random.default_rng(7)
    center = electrode = None
    for name, counts, scale in SPONTANEOUS_FOLDERS:
        for n, count in enumerate(counts, start=1):
            onsets = 150 + np.sort(rng.choice(np.arange(0, 1200, 200), count, replace=False)) + rng.integers(0, 60, count)
            planted = [(int(t), int(rng.integers(15, 112)), int(rng.integers(60, 112)), scale * rng.uniform(0.02, 0.05),
                        rng.uniform(6, 11)) for t in onsets]
            center, electrode = planted_example(recordings, root / name, planted, f"no{n}.tif")
    selections = Selections(root, RoiSettings())
    for name, _, _ in SPONTANEOUS_FOLDERS:
        selections.folders[name] = FolderSelection(electrode.shape, center, RoiSettings().roi_radius_px, electrode,
                                                   reviewed=True)
    selections.save(root.parent / "roi_selections.json")
    window = SpontaneousAnalysisWindow(user_folder=output / "detectors", workers=4)
    window.resize(1400, 760)
    window.recordings_input.path.setText(str(root))
    window.load_recordings_folder()
    window.roi_input.path.setText(str(root.parent / "roi_selections.json"))
    window.load_roi_file()
    window.output.path.setText(str(output / "spontaneous_demo" / "Spontaneous"))
    window.output_changed()
    window.start()
    window.worker.wait()
    app.processEvents()
    shown_as(window.recordings_input, "C:/Users/you/Recordings")
    shown_as(window.roi_input, "C:/Users/you/EMA results/roi_selections.json")
    shown_as(window.output, "C:/Users/you/EMA results/Spontaneous")
    window.show()
    save(window, "spontaneous_analysis.png")
    window.close()
    EXAMPLES.mkdir(exist_ok=True)
    for name in (PER_EVENT, SPONTANEOUS_PER_SLICE):
        shutil.copyfile(output / "spontaneous_demo" / "Spontaneous" / name, EXAMPLES / ("Example - " + name))
        print("saved Example -", name)


if __name__ == "__main__":
    main()
