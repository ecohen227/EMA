"""The windows, driven without a screen."""

from dataclasses import replace

import numpy as np
import pytest
from matplotlib.backend_bases import MouseEvent
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton

from ema import user_settings
from ema.launcher import Launcher
from ema.roi_selection import FILE_NAME, Selections
from ema.roi_selection.selections import AUTOMATIC, MANUAL
from ema.roi_selection.setup_dialog import SetupDialog
from ema.roi_selection.window import VIEW_BASELINE, VIEW_MEAN, VIEW_MOVIE, RoiSelectionWindow

from conftest import CENTER


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def own_user_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "FILE", tmp_path / "user" / "settings.json")


@pytest.fixture
def window(app, recordings, tmp_path):
    window = RoiSelectionWindow(Selections(recordings), tmp_path)
    window.show()
    window.folder_list.setCurrentRow(1)  # the "input output" folder
    window.image.draw()
    yield window
    window.close()


def mouse(view, kind, x, y, button=1):
    """Send a matplotlib mouse event at image position (x, y)."""
    px, py = view.axes.transData.transform((x, y))
    view.callbacks.process(kind, MouseEvent(kind, view, px, py, button))


def drag(view, points, button=1):
    mouse(view, "button_press_event", *points[0], button)
    for point in points[1:]:
        mouse(view, "motion_notify_event", *point, button)
    mouse(view, "button_release_event", *points[-1], button)


def saved(window):
    return Selections.load(window.output_folder / FILE_NAME)


def test_opening_a_folder_detects_and_saves_it(window, io_folder):
    selection = window.selection
    assert window.recording_box.currentText() == "200uA.tif"
    assert selection.roi_source == AUTOMATIC and selection.electrode_mask.any()
    assert np.hypot(selection.roi_center[0] - CENTER[0], selection.roi_center[1] - CENTER[1]) <= 1.5
    assert saved(window).of(io_folder).roi_center == selection.roi_center


def test_trace_plot_is_rescaled_for_each_recording(window):
    tall = window.trace.axes.get_ylim()[1]
    window.recording_box.setCurrentIndex(3)  # no1.tif: no response
    assert window.trace.axes.get_ylim()[1] < tall / 3


def test_every_view_can_be_shown(window):
    for view in (VIEW_MEAN, VIEW_BASELINE, VIEW_MOVIE):
        window.view_box.setCurrentText(view)
    window.slider.setValue(120)
    assert window.movie_row.isVisible() and "120" in window.frame_label.text()


def test_dragging_moves_the_roi(window, io_folder):
    x, y = window.selection.roi_center
    drag(window.image, [(x + 2, y + 1), (x + 8, y + 1), (x + 12, y - 9)])  # grabbed inside the circle: no jump
    assert window.selection.roi_center == (x + 10, y - 10)
    assert saved(window).of(io_folder).roi_source == MANUAL

    drag(window.image, [(10, 50)])  # a click outside the circle centres the ROI there
    assert window.selection.roi_center == (10, 50)

    window.use_automatic_roi()
    assert window.selection.roi_center == (x, y) and window.selection.roi_source == AUTOMATIC


def test_the_roi_stays_inside_the_image(window):
    drag(window.image, [(30, 30), (63.4, 63.4)])
    assert window.selection.roi_center == (63, 63)


def test_redrawing_the_electrode(window, io_folder):
    square = [(40, 40), (50, 40), (50, 50), (40, 50)]
    before = window.selection.electrode_mask.copy()
    window.electrode_tool.setChecked(True)

    drag(window.image, square)  # left button adds
    assert window.selection.electrode_mask[45, 45] and window.selection.electrode_source == MANUAL
    assert saved(window).of(io_folder).electrode_mask[45, 45]

    drag(window.image, square, button=3)  # right button removes
    assert np.array_equal(window.selection.electrode_mask, before)

    window.remove_electrode()
    assert not window.selection.electrode_mask.any()
    window.use_automatic_electrode()
    assert np.array_equal(window.selection.electrode_mask, before) and window.selection.electrode_source == AUTOMATIC


def test_flags(window, io_folder):
    window.reason.setText("no response")
    window.flag_recording(True)
    assert saved(window).of(io_folder).flagged_files == {"200uA.tif": "no response"}
    assert window.recording_box.currentText().startswith("⚑")

    window.recording_box.setCurrentIndex(0)
    assert not window.flag_box.isChecked() and window.reason.text() == ""
    window.flag_folder()
    assert len(window.selection.flagged_files) == 4

    window.flag_recording(False)
    assert not window.selection.is_flagged("100uA.tif")


def test_accept_and_next(window, io_folder):
    window.folder_list.setCurrentRow(0)
    window.accept_and_next()
    assert window.folder_list.currentRow() == 1
    assert window.folder_list.item(0).text().startswith("✓")
    assert "1 of 2" in window.progress_label.text()
    window.accept_and_next()  # the last folder: stays, and says so
    assert window.folder_list.currentRow() == 1 and "last folder" in window.status.text()


def test_detect_all(app, recordings, tmp_path):
    window = RoiSelectionWindow(Selections(recordings), tmp_path)
    assert len(window.selections.folders) == 1
    window.detect_all()
    assert len(saved(window).folders) == 2


def test_new_settings_detect_untouched_folders_again(window, train_folder, io_folder, monkeypatch):
    window.detect_all()
    window.move_roi(20, 20)
    window.drop_roi()
    new = replace(window.settings, roi_radius_px=8, find_electrode=False)

    def fake_dialog(self):
        self.selections.change_settings(new)
        return True

    monkeypatch.setattr(SetupDialog, "exec_", fake_dialog)
    window.change_settings()
    assert window.selection.roi_center == (20, 20) and window.selection.roi_radius_px == 8
    assert window.selections.of(train_folder) is None  # forgotten until it is opened or detected again
    window.folder_list.setCurrentRow(0)
    assert not window.selection.electrode_mask.any()


def test_continuing_saved_selections(window, app, recordings, io_folder):
    window.move_roi(20, 20)
    window.drop_roi()
    again = RoiSelectionWindow(saved(window), window.output_folder)
    again.folder_list.setCurrentRow(1)
    assert again.selection.roi_center == (20, 20) and again.selection.roi_source == MANUAL


def test_folder_that_cannot_be_detected_says_why(app, recordings, tmp_path):
    settings = replace(Selections(recordings).settings, search_frames=[5000, 6000])
    window = RoiSelectionWindow(Selections(recordings, settings), tmp_path)
    assert "search window" in window.status.text()
    assert not window.accept_button.isEnabled()


def test_setup_dialog(app, recordings, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog = SetupDialog()
    dialog.recordings.path.setText(str(recordings))

    dialog.output.path.setText(str(recordings / "results"))
    dialog.accept()
    assert "outside the recordings folder" in warnings[-1] and dialog.selections is None

    dialog.output.path.setText(str(tmp_path / "results"))
    dialog.form.inputs["roi_radius_px"].setValue(15)
    dialog.form.inputs["detection_files"].setText("300uA.tif, 400uA")
    dialog.accept()
    assert dialog.selections.settings.roi_radius_px == 15
    assert dialog.selections.settings.detection_files == ["300uA", "400uA"]
    assert dialog.output_folder == tmp_path / "results"
    assert user_settings.remembered("roi_recordings_folder") == str(recordings)


def test_setup_dialog_continues_saved_selections(window, app, recordings):
    window.move_roi(20, 20)
    window.drop_roi()
    dialog = SetupDialog()
    dialog.recordings.path.setText(str(recordings))
    dialog.output.path.setText(str(window.output_folder))
    dialog.show_saved_settings()
    assert "already holds selections" in dialog.note.text()
    dialog.accept()
    assert dialog.selections.folders["Animal 1/Slice 1/input output"].roi_center == (20, 20)


def test_launcher_offers_four_packages(app):
    launcher = Launcher()
    packages = [b for b in launcher.findChildren(QPushButton) if "\n" in b.text()]
    assert len(packages) == 4
    assert [b.isEnabled() for b in packages] == [True, False, False, False]
