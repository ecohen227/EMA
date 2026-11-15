from dataclasses import replace

import numpy as np
import pytest

from ema.recordings import list_recordings, load_stack
from ema.roi_selection import RoiSettings, detect_folder, roi_mask, roi_trace
from ema.roi_selection.detection import detection_files, peak_frame

from conftest import CENTER, ELECTRODE, STIM_FRAME, make_recording

SETTINGS = RoiSettings()


def test_roi_is_found_at_the_strongest_response(io_folder):
    detection = detect_folder(io_folder, SETTINGS)
    assert detection.files == ["200uA.tif", "300uA.tif"]
    assert np.hypot(detection.center[0] - CENTER[0], detection.center[1] - CENTER[1]) <= 1.5
    assert 0.3 < detection.peak_response < 0.6


def test_electrode_is_found(io_folder):
    found = detect_folder(io_folder, SETTINGS).electrode
    assert (found & ELECTRODE).sum() >= 0.95 * ELECTRODE.sum()
    assert found.sum() <= 1.6 * ELECTRODE.sum()  # one pixel wider all round, not more
    assert found[:, 0].any()  # the mask reaches the image edge


def test_electrode_settings_are_used(io_folder):
    def electrode(**changes):
        return detect_folder(io_folder, replace(SETTINGS, **changes)).electrode

    assert not electrode(find_electrode=False).any()
    assert not electrode(electrode_edge="right").any()
    assert electrode(electrode_edge="any").any()
    assert not electrode(electrode_min_length_px=60).any()
    assert not electrode(electrode_max_distance_px=5).any()
    assert electrode(electrode_grow_px=0).sum() < electrode(electrode_grow_px=3).sum()


def test_folder_without_named_files_uses_every_stimulated_recording(train_folder):
    names = [path.name for path in detection_files(list_recordings(train_folder), SETTINGS)]
    assert names == ["hi1.tif"]  # not no1.tif, and not 'hi1 red.tif'
    detection = detect_folder(train_folder, SETTINGS)
    assert np.hypot(detection.center[0] - CENTER[0], detection.center[1] - CENTER[1]) <= 1.5


def test_folder_without_stimulated_recordings_is_refused(tmp_path):
    make_recording(tmp_path / "no1.tif", response=0.0)
    with pytest.raises(ValueError, match="no stimulated recordings"):
        detect_folder(tmp_path, SETTINGS)


def test_window_beyond_the_recording_is_refused(io_folder):
    with pytest.raises(ValueError, match="search window"):
        detect_folder(io_folder, replace(SETTINGS, search_frames=[5000, 6000]))


def test_peak_frame_and_trace(io_folder):
    stack = load_stack(io_folder / "300uA.tif")
    assert abs(peak_frame(stack, SETTINGS) - STIM_FRAME) <= 3
    trace = roi_trace(stack, CENTER, 10, SETTINGS)
    assert abs(trace[: STIM_FRAME - 5].mean()) < 0.5
    assert trace.max() > 20


def test_roi_mask_is_a_disk():
    mask = roi_mask((64, 64), (30, 20), 5)
    assert mask[20, 30] and mask[20, 35] and not mask[20, 36]
    assert mask.sum() == 81
