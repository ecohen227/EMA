import csv
from dataclasses import replace

import numpy as np
import pytest

from ema.roi_selection import FolderSelection, RoiSettings, Selections, detect_folder
from ema.roi_selection.selections import MANUAL, mask_to_text, text_to_mask


def test_mask_text_round_trip():
    rng = np.random.default_rng(0)
    for mask in (rng.random((20, 30)) > 0.5, np.zeros((5, 5), bool), np.ones((5, 5), bool)):
        assert np.array_equal(text_to_mask(mask_to_text(mask), mask.shape), mask)
    assert mask_to_text(np.array([[False, True, True], [True, False, True]])) == "0:1-2 1:0-0 1:2-2"


@pytest.fixture
def selections(recordings, io_folder, train_folder):
    settings = RoiSettings()
    selections = Selections(recordings, settings)
    for folder in (io_folder, train_folder):
        selection = FolderSelection.from_detection(detect_folder(folder, settings), settings)
        selections.folders[selections.name_of(folder)] = selection
    return selections


def test_save_and_load(selections, io_folder, tmp_path):
    edited = selections.of(io_folder)
    edited.roi_center, edited.roi_source = (12, 34), MANUAL
    edited.flagged_files["100uA.tif"] = "no response"
    edited.reviewed = True
    selections.save(tmp_path / "roi_selections.json")

    loaded = Selections.load(tmp_path / "roi_selections.json")
    assert loaded.settings == selections.settings
    assert set(loaded.folders) == {"Animal 1/Slice 1/input output", "Animal 1/Slice 1/11p at 200uA"}
    for name, saved in selections.folders.items():
        back = loaded.folders[name]
        assert np.array_equal(back.electrode_mask, saved.electrode_mask)
        assert np.array_equal(back.roi_mask(), saved.roi_mask())
        assert replace(back, electrode_mask=None) == replace(saved, electrode_mask=None)
    assert loaded.of(io_folder).is_flagged("100uA.tif") and not loaded.of(io_folder).is_flagged("200uA.tif")


def test_other_json_files_are_refused(tmp_path):
    (tmp_path / "other.json").write_text('{"hello": 1}')
    with pytest.raises(ValueError, match="not an EMA ROI file"):
        Selections.load(tmp_path / "other.json")


def test_new_settings_keep_only_hand_adjusted_folders(selections, io_folder, train_folder):
    selections.of(io_folder).roi_source = MANUAL
    selections.change_settings(replace(selections.settings, roi_radius_px=12))
    assert selections.of(train_folder) is None
    assert selections.of(io_folder).roi_radius_px == 12


def test_same_settings_change_nothing(selections):
    selections.change_settings(RoiSettings())
    assert len(selections.folders) == 2


def test_export_table(selections, io_folder, tmp_path):
    selections.of(io_folder).flagged_files = {"100uA.tif": "weak", "no1.tif": ""}
    selections.export_table(tmp_path / "table.csv")
    with open(tmp_path / "table.csv", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["folder"] for row in rows] == sorted(selections.folders)
    assert rows[1]["flagged_files"] == "100uA.tif: weak; no1.tif"
