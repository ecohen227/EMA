"""The windows, driven without a screen."""

from dataclasses import replace

import numpy as np
import pytest
from matplotlib.backend_bases import MouseEvent
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox, QPushButton

from ema import user_settings
from ema.launcher import PACKAGES, WORKFLOWS, Launcher
from ema.roi_selection import FILE_NAME, Selections
from ema.roi_selection.selections import AUTOMATIC, MANUAL
from ema.roi_selection.setup_dialog import SetupDialog
from ema.roi_selection.window import MEAN, VIEW_BASELINE, VIEW_MOVIE, VIEW_RESPONSE, RoiSelectionWindow

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
    window.finish_strip()
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


# ---------------------------------------------------------------------------
# Opening folders and recordings
# ---------------------------------------------------------------------------


def test_opening_a_folder_detects_and_saves_it(window, io_folder):
    selection = window.selection
    assert selection.roi_source == AUTOMATIC and selection.electrode_mask.any()
    assert np.hypot(selection.roi_center[0] - CENTER[0], selection.roi_center[1] - CENTER[1]) <= 1.5
    assert saved(window).of(io_folder).roi_center == selection.roi_center


def test_a_folder_opens_on_its_mean_recording(window):
    assert window.recording == MEAN
    assert window.recording_box.currentText() == "Mean of 200uA, 300uA"
    assert not window.flag_box.isEnabled() and not window.reason.isEnabled()  # a mean cannot be flagged

    window.choose_recording("100uA.tif")
    assert window.recording == "100uA.tif" and window.flag_box.isEnabled()
    assert window.trace.axes.get_title() == "100uA.tif"


def test_trace_plot_is_rescaled_for_each_recording(window):
    tall = window.trace.axes.get_ylim()[1]
    window.choose_recording("no1.tif")
    assert window.trace.axes.get_ylim()[1] < tall / 3


def test_slider_works_in_every_view(window):
    assert window.slider.value() == window.peak and "the peak" in window.frame_label.text()
    at_peak = window.image.image.get_array().copy()

    window.slider.setValue(20)  # long before the stimulation: no response yet
    assert window.view_box.currentText() == VIEW_RESPONSE
    assert window.image.image.get_array().max() < at_peak.max() / 3
    assert window.trace.frame_marker.get_xdata()[0] == 20 and "Frame 20" in window.frame_label.text()

    window.view_box.setCurrentText(VIEW_MOVIE)
    assert window.slider.isVisible() and window.slider.isEnabled()
    assert np.array_equal(window.image.image.get_array(), window.stack[20])

    window.view_box.setCurrentText(VIEW_BASELINE)
    assert window.slider.isVisible() and not window.slider.isEnabled()  # the baseline image has no time
    assert "Mean of frames 10 to 94" in window.frame_label.text()


# ---------------------------------------------------------------------------
# ROI and electrode
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# The strip of all recordings, and flags
# ---------------------------------------------------------------------------


def test_strip_shows_every_recording_but_the_hidden(window):
    assert window.hide_box.text() == "no"  # the unstimulated recordings are hidden unless the user says otherwise
    assert list(window.strip.cards) == [MEAN, "100uA.tif", "200uA.tif", "300uA.tif"]
    window.hide_box.setText("")
    window.hide_box.editingFinished.emit()
    window.finish_strip()
    cards = window.strip.cards
    assert list(cards) == [MEAN, "100uA.tif", "200uA.tif", "300uA.tif", "no1.tif"]
    assert all(card.picture is not None for card in cards.values())
    peaks = {name: float(card.caption.rstrip(" %")) for name, card in cards.items()}
    assert peaks["300uA.tif"] > peaks["200uA.tif"] > peaks["100uA.tif"] > 5 > peaks["no1.tif"]
    assert cards[MEAN].selected and not cards["100uA.tif"].selected


def test_strip_follows_the_roi(window):
    before = window.strip.cards["300uA.tif"].trace.max()
    drag(window.image, [(8, 8)])  # far from the response
    window.finish_strip()
    assert window.strip.roi == ((8, 8), 20)
    assert window.strip.cards["300uA.tif"].trace.max() < before / 2


def test_clicking_a_card_shows_its_recording(window):
    QTest.mouseClick(window.strip.cards["300uA.tif"], Qt.LeftButton)
    assert window.recording == "300uA.tif" and window.recording_box.currentText() == "300uA.tif"
    assert window.strip.cards["300uA.tif"].selected and not window.strip.cards[MEAN].selected


def test_right_clicking_a_card_flags_it(window, io_folder):
    card = window.strip.cards["100uA.tif"]
    QTest.mouseClick(card, Qt.RightButton)
    assert card.flagged and window.recording == "100uA.tif" and window.flag_box.isChecked()
    assert saved(window).of(io_folder).flagged_files == {"100uA.tif": ""}
    assert window.recording_box.currentText() == "⚑ 100uA.tif"
    assert window.folder_list.currentItem().text().startswith("⚑")

    QTest.keyClicks(window.reason, "weak")  # a reason can be typed straight away
    assert saved(window).of(io_folder).flagged_files == {"100uA.tif": "weak"}

    QTest.mouseClick(card, Qt.RightButton)
    assert not card.flagged and not window.selection.flagged_files

    QTest.mouseClick(window.strip.cards[MEAN], Qt.RightButton)  # the mean cannot be flagged
    assert not window.selection.flagged_files


def test_flag_box_and_flag_all(window, io_folder, monkeypatch):
    window.choose_recording("200uA.tif")
    window.reason.setText("no response")
    window.flag_recording(True)
    assert saved(window).of(io_folder).flagged_files == {"200uA.tif": "no response"}

    window.choose_recording("100uA.tif")
    assert not window.flag_box.isChecked() and window.reason.text() == ""

    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("slice moved", True))
    window.flag_folder()
    everything = ["100uA.tif", "200uA.tif", "300uA.tif", "no1.tif"]
    assert window.selection.flagged_files == dict.fromkeys(everything, "slice moved")
    assert all(card.flagged for name, card in window.strip.cards.items() if name != MEAN)

    window.flag_recording(False)
    assert not window.selection.is_flagged("100uA.tif")


# ---------------------------------------------------------------------------
# Moving on, settings, continuing
# ---------------------------------------------------------------------------


def test_accept_and_next(window, io_folder):
    window.folder_list.setCurrentRow(1)
    window.accept_and_next()  # the last folder: on to the first one, which is not reviewed yet
    assert window.folder_list.currentRow() == 0
    assert window.folder_list.item(1).text().startswith("✓")
    assert "1 of 2" in window.progress_label.text()
    window.accept_and_next()  # every folder reviewed: stays, and says so
    assert window.folder_list.currentRow() == 0 and "All 2 folders are reviewed" in window.status.text()


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
    assert not window.accept_button.isEnabled() and not window.strip.cards


# ---------------------------------------------------------------------------
# Setup dialog and launcher
# ---------------------------------------------------------------------------


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


def test_electrode_settings_are_greyed_out_when_the_electrode_is_not_looked_for(app):
    form = SetupDialog().form
    electrode_settings = [name for name in form.inputs if name.startswith("electrode_")]
    assert len(electrode_settings) == 7
    assert all(form.inputs[name].isEnabled() and form.labels[name].isEnabled() for name in electrode_settings)

    form.inputs["find_electrode"].setChecked(False)
    assert not any(form.inputs[name].isEnabled() or form.labels[name].isEnabled() for name in electrode_settings)
    assert form.inputs["roi_radius_px"].isEnabled() and form.inputs["find_electrode"].isEnabled()

    form.show_settings(replace(form.settings(), find_electrode=True))
    assert all(form.inputs[name].isEnabled() for name in electrode_settings)


def test_setup_dialog_shows_a_live_example(app, recordings, io_folder):
    dialog = SetupDialog()
    dialog.recordings.path.setText(str(recordings))
    dialog.recordings.changed.emit()
    preview = dialog.preview
    assert preview.folder_box.count() == 2
    preview.folder_box.setCurrentIndex(1)  # the "input output" folder
    assert f"ROI centre ({CENTER[0]}, {CENTER[1]})" in preview.message.text()
    assert preview.trace.axes.get_title() == "Mean of 200uA, 300uA"
    assert preview.image.roi.radius == 20

    dialog.form.inputs["roi_radius_px"].setValue(9)
    dialog.form.inputs["find_electrode"].setChecked(False)
    assert dialog.preview_timer.isActive()  # the example follows a moment after an edit
    dialog.show_example()
    assert preview.image.roi.radius == 9
    assert "Electrode: 0 pixels" in preview.message.text()

    dialog.form.inputs["search_frames"].setValue([5000, 6000])
    dialog.show_example()
    assert "search window" in preview.message.text()

    dialog.form.inputs["baseline_frames"].setValue([50, 20])
    dialog.show_example()
    assert "first frame must be smaller" in preview.message.text()


def test_settings_example_starts_with_the_open_folder(window, io_folder):
    dialog = SetupDialog(window, window.selections, window.output_folder, example_folder=io_folder)
    assert dialog.preview.folder_box.currentData() == io_folder
    assert "ROI centre" in dialog.preview.message.text()


def test_launcher_offers_every_package_in_order(app):
    launcher = Launcher()
    packages = [b.accessibleName() for b in launcher.findChildren(QPushButton) if b.accessibleName()]
    assert packages == [f"{step}  {name}" for _, _, group in WORKFLOWS for step, (name, _, _) in enumerate(group, start=1)]
    assert len(packages) == len(PACKAGES) == 5


def test_recordings_hidden_in_the_strip_are_not_read_but_can_be_shown(app, recordings, tmp_path):
    user_settings.remember(roi_hide_in_strip="UA, red")  # remembered from an earlier session; upper/lower case alike
    window = RoiSelectionWindow(Selections(recordings), tmp_path)
    window.show()
    window.folder_list.setCurrentRow(1)
    assert window.hide_box.text() == "UA, red" and list(window.strip.cards) == [MEAN, "no1.tif"]
    window.finish_strip()
    reading = {path.name for path in window.load._reading}
    assert not reading & {"100uA.tif", "200uA.tif", "300uA.tif"}  # hidden: not read ahead
    window.choose_recording("300uA.tif")  # a hidden recording can still be shown and flagged
    assert window.recording == "300uA.tif" and window.stack is not None
    assert not any(card.selected for card in window.strip.cards.values())
    window.flag_recording(True)
    assert window.selection.is_flagged("300uA.tif")

    window.hide_box.setText(" no ,, ")
    window.hide_box.editingFinished.emit()
    assert window.hide_box.text() == "no" and user_settings.remembered("roi_hide_in_strip") == "no"
    assert list(window.strip.cards) == [MEAN, "100uA.tif", "200uA.tif", "300uA.tif"]
    window.finish_strip()
    assert window.strip.cards["300uA.tif"].selected and window.strip.cards["300uA.tif"].flagged
    assert all(card.picture is not None for card in window.strip.cards.values())
    window.close()


def test_closing_while_the_strip_is_filled_stops_it(app, recordings, tmp_path):
    window = RoiSelectionWindow(Selections(recordings), tmp_path)
    window.show()
    window.folder_list.setCurrentRow(1)
    assert window.cards_to_fill
    window.close()
    assert not window.cards_to_fill and not window.strip_timer.isActive()
    window.fill_next_card()  # a timer event already on its way does nothing
