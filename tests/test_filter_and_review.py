"""The folder filter, and what a settings change does to folders that were already reviewed."""

from dataclasses import replace

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox

from ema import user_settings
from ema.roi_selection import FILE_NAME, FolderSelection, RoiSettings, Selections, detect_folder
from ema.roi_selection.selections import AUTOMATIC, MANUAL, folder_matches
from ema.roi_selection.setup_dialog import RoiSettingsForm, SetupDialog
from ema.roi_selection.window import RoiSelectionWindow

IO, TRAIN = "Animal 1/Slice 1/input output", "Animal 1/Slice 1/11p at 200uA"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def own_user_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "FILE", tmp_path / "user" / "settings.json")


@pytest.fixture
def selections(recordings, io_folder, train_folder):
    """Both folders detected and reviewed; the ROI of the input-output folder was moved by hand."""
    settings = RoiSettings()
    selections = Selections(recordings, settings)
    for folder in (io_folder, train_folder):
        selection = FolderSelection.from_detection(detect_folder(folder, settings), settings)
        selection.reviewed = True
        selections.folders[selections.name_of(folder)] = selection
    selections.folders[IO].roi_center, selections.folders[IO].roi_source = (20, 20), MANUAL
    return selections


def answer(monkeypatch, reply):
    """Answer every question box with `reply` and collect the questions."""
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: questions.append(args[2]) or reply)
    return questions


# ---------------------------------------------------------------------------
# The folder filter
# ---------------------------------------------------------------------------


def test_folder_matches():
    name = "Females/LKI HET F5341/CTRL 2H/Slice 1/11p at 200uA"
    assert folder_matches(name, [], [])
    assert folder_matches(name, ["11P"], []) and not folder_matches(name, ["input"], [])
    assert folder_matches(name, ["input", "11p"], [])  # one of the words is enough
    assert not folder_matches(name, ["11p"], ["ctrl"]) and folder_matches(name, ["11p"], ["4ap", "wash"])


def test_only_matching_folders_are_listed(selections, io_folder, train_folder):
    assert selections.recording_folders() == [train_folder, io_folder]
    selections.change_folder_filter(["input"], [])
    assert selections.recording_folders() == [io_folder]
    selections.change_folder_filter([], ["INPUT"])
    assert selections.recording_folders() == [train_folder]


def test_changing_the_filter_forgets_folders_that_no_longer_pass(selections, tmp_path):
    selections.change_folder_filter(["11p"], ["wash"])
    assert list(selections.folders) == [TRAIN] and selections.folders[TRAIN].reviewed  # no review is undone

    selections.save(tmp_path / FILE_NAME)
    loaded = Selections.load(tmp_path / FILE_NAME)
    assert loaded.only_folders_with == ["11p"] and loaded.skip_folders_with == ["wash"]


def test_window_lists_only_matching_folders(app, selections, train_folder, tmp_path):
    selections.change_folder_filter(["11p"], [])
    window = RoiSelectionWindow(selections, tmp_path)
    assert window.folders == [train_folder] and window.folder_list.count() == 1
    assert "1 of 1" in window.progress_label.text()


def test_setup_dialog_counts_and_saves_the_filter(app, recordings, train_folder, tmp_path):
    dialog = SetupDialog()
    dialog.recordings.path.setText(str(recordings))
    dialog.recordings.changed.emit()
    assert "2 of 2 recording folders" in dialog.match_count.text()

    dialog.filter.only_with.setText("11P, nothing")
    assert "1 of 2 recording folders" in dialog.match_count.text()
    assert dialog.preview.folder_box.count() == 1 and dialog.preview.folder_box.currentData() == train_folder

    dialog.filter.skip_with.setText("slice")
    assert "0 of 2 recording folders" in dialog.match_count.text()
    assert "No recording folder" in dialog.preview.message.text()

    dialog.recordings.path.setText("C:/another folder, still being typed")
    dialog.filter.skip_with.setText("sl")  # the filter keeps working on the folders found so far
    assert "0 of 2 recording folders" in dialog.match_count.text()
    dialog.recordings.path.setText(str(recordings))

    dialog.filter.skip_with.setText("")
    dialog.output.path.setText(str(tmp_path / "results"))
    dialog.accept()
    assert dialog.selections.only_folders_with == ["11P", "nothing"]
    assert dialog.selections.recording_folders() == [train_folder]


def test_setup_dialog_opens_on_saved_selections_with_a_filter(app, selections, recordings, tmp_path):
    selections.change_folder_filter(["11p"], [])
    selections.save(tmp_path / FILE_NAME)
    user_settings.remember(roi_recordings_folder=str(recordings), roi_output_folder=str(tmp_path))
    dialog = SetupDialog()  # the saved filter is shown before the folders are looked up
    assert dialog.filter.words() == (["11p"], [])
    assert "1 of 2 recording folders" in dialog.match_count.text()


def test_setup_dialog_warns_before_saved_folders_are_left_out(app, selections, monkeypatch, tmp_path):
    dialog = SetupDialog(None, selections, tmp_path)
    dialog.filter.only_with.setText("11p")

    questions = answer(monkeypatch, QMessageBox.No)
    dialog.accept()
    assert "1 saved folder(s) do not pass the folder filter" in questions[-1]
    assert not dialog.result() and len(selections.folders) == 2

    answer(monkeypatch, QMessageBox.Yes)
    dialog.accept()
    assert dialog.result() and list(selections.folders) == [TRAIN]


def test_window_follows_a_new_filter(app, selections, train_folder, monkeypatch, tmp_path):
    window = RoiSelectionWindow(selections, tmp_path)
    window.folder_list.setCurrentRow(1)

    def fake_dialog(self):
        self.selections.change_folder_filter(["11p"], [])
        return True

    monkeypatch.setattr(SetupDialog, "exec_", fake_dialog)
    window.change_settings()
    assert window.folders == [train_folder] and window.folder_list.count() == 1
    assert window.folder == train_folder and window.selection.reviewed  # still reviewed: no setting changed

    monkeypatch.setattr(SetupDialog, "exec_", lambda self: self.selections.change_folder_filter(["nothing"], []) or True)
    window.change_settings()
    assert window.folder_list.count() == 0 and "folder filter" in window.status.text()


# ---------------------------------------------------------------------------
# A settings change
# ---------------------------------------------------------------------------


def test_electrode_settings_are_greyed_out_when_settings_open_without_electrode(app, selections, tmp_path):
    form = RoiSettingsForm(replace(RoiSettings(), find_electrode=False))
    assert not form.inputs["electrode_threshold"].isEnabled() and not form.labels["electrode_threshold"].isEnabled()

    selections.change_settings(replace(selections.settings, find_electrode=False))
    dialog = SetupDialog(None, selections, tmp_path)  # as when Settings… is opened a second time
    assert not dialog.form.inputs["electrode_edge"].isEnabled()
    dialog.form.inputs["find_electrode"].setChecked(True)
    assert dialog.form.inputs["electrode_edge"].isEnabled()


def test_settings_sections_start_closed_and_open_on_a_click(app):
    form = RoiSettingsForm(RoiSettings())
    assert list(form.sections) == ["ROI", "Timing", "Electrode", "Display"]
    assert all(section.content.isHidden() for section in form.sections.values())

    electrode = form.sections["Electrode"]
    electrode.heading.click()
    assert not electrode.content.isHidden() and form.sections["ROI"].content.isHidden()
    electrode.heading.click()
    assert electrode.content.isHidden()


def test_closed_section_says_when_a_setting_is_not_at_its_default(app):
    form = RoiSettingsForm(replace(RoiSettings(), electrode_threshold=0.8, electrode_grow_px=2, roi_radius_px=15))
    assert form.sections["Electrode"].heading.text() == "Electrode   (2 changed from the default)"
    assert form.sections["ROI"].heading.text() == "ROI   (1 changed from the default)"
    assert form.sections["Timing"].heading.text() == "Timing"

    form.inputs["roi_radius_px"].setValue(20)
    assert form.sections["ROI"].heading.text() == "ROI"
    form.show_settings(RoiSettings())  # what Restore defaults does
    assert form.sections["Electrode"].heading.text() == "Electrode"


def test_after_a_settings_change_every_folder_must_be_reviewed_again(selections, io_folder, tmp_path):
    new = replace(selections.settings, roi_radius_px=12, find_electrode=False)
    selections.change_settings(new)

    assert list(selections.folders) == [IO]  # the untouched folder will simply be detected again
    kept = selections.folders[IO]
    assert not kept.reviewed and kept.needs_detection
    assert kept.roi_center == (20, 20) and kept.roi_source == MANUAL and kept.roi_radius_px == 12

    selections.save(tmp_path / FILE_NAME)  # a folder waiting for detection can be saved and loaded
    loaded = Selections.load(tmp_path / FILE_NAME).folders[IO]
    assert loaded.needs_detection and loaded.roi_center == (20, 20)

    loaded.use_detection(detect_folder(io_folder, new))
    assert not loaded.needs_detection
    assert loaded.roi_center == (20, 20)  # set by hand: kept
    assert loaded.electrode_source == AUTOMATIC and not loaded.electrode_mask.any()  # automatic: found again


def test_window_detects_kept_folders_again(app, selections, io_folder, monkeypatch, tmp_path):
    window = RoiSelectionWindow(selections, tmp_path)
    new = replace(selections.settings, find_electrode=False)
    monkeypatch.setattr(SetupDialog, "exec_", lambda self: self.selections.change_settings(new) or True)
    window.change_settings()
    assert "0 of 2" in window.progress_label.text()

    window.detect_all()
    saved = Selections.load(tmp_path / FILE_NAME)
    assert len(saved.folders) == 2 and not any(s.needs_detection or s.reviewed for s in saved.folders.values())
    assert saved.folders[IO].roi_center == (20, 20) and not saved.folders[IO].electrode_mask.any()

    window.folder_list.setCurrentRow(1)
    assert window.selection.roi_source == MANUAL and not np.any(window.selection.electrode_mask)


def test_setup_dialog_warns_before_reviews_are_lost(app, selections, monkeypatch, tmp_path):
    dialog = SetupDialog(None, selections, tmp_path)
    dialog.form.inputs["smoothing_px"].setValue(3.0)

    questions = answer(monkeypatch, QMessageBox.No)
    dialog.accept()
    assert "all 2 reviewed folder(s) will have to be reviewed again" in questions[-1]
    assert not dialog.result() and all(s.reviewed for s in selections.folders.values())

    answer(monkeypatch, QMessageBox.Yes)
    dialog.accept()
    assert dialog.result() and selections.settings.smoothing_px == 3.0
    assert not any(s.reviewed for s in selections.folders.values())


def test_setup_dialog_asks_nothing_when_nothing_is_lost(app, selections, monkeypatch, tmp_path):
    questions = answer(monkeypatch, QMessageBox.No)
    dialog = SetupDialog(None, selections, tmp_path)
    dialog.accept()
    assert dialog.result() and not questions
