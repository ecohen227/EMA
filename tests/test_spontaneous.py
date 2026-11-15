"""The spontaneous-event detector, its measures, the detector file and the configurator, on synthetic movies."""

import json
from dataclasses import replace

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from ema import user_settings
from ema.spontaneous import detector as library
from ema.spontaneous.detection import drop_echoes, kernel, template, tissue_mask, detect
from ema.spontaneous.detector import Detector, detector_v5
from ema.spontaneous.measure_details import EVENT_DETAILS, RECORDING_DETAILS, SLICE_DETAILS
from ema.spontaneous.measures import (
    EVENT_KEYS,
    RECORDING_KEYS,
    SLICE_KEYS,
    TRACE_BEFORE,
    clustering_index,
    measure_events,
    measure_recording,
    summarise_slice,
    time_course,
)
from ema.spontaneous.settings import DetectorSettings

FRAME_MS = 4.849
SHAPE = (96, 96)
EVENTS = [(300, 30, 30, 0.06), (600, 70, 60, 0.04)]  # onset frame (in the movie), row, column, peak dF/F
SIGMA_PX = 6.0  # 96 µm


def movie(events=EVENTS, frames=900, seed=0, sign=1.0):
    """Flat tissue with bleaching and 2 % noise per pixel and frame, and Gaussian events with dLight kinetics."""
    rng = np.random.default_rng(seed)
    t_ms = np.arange(frames) * FRAME_MS
    rows, cols = np.indices(SHAPE)
    signal = np.zeros((frames, *SHAPE), np.float32)
    for onset, row, col, peak in events:
        shape = np.exp(-((cols - col) ** 2 + (rows - row) ** 2) / (2 * SIGMA_PX**2))
        signal += sign * peak * kernel(t_ms - (onset + 1) * FRAME_MS, 200.0, 12.0)[:, None, None].astype(np.float32) * shape
    bleach = np.exp(-t_ms / 20000)[:, None, None]
    stack = 1000 * bleach * (1 + signal) * (1 + rng.normal(0, 0.02, (frames, *SHAPE)))
    return stack[1:].astype(np.float32)  # the first frame of a file is dropped on loading


@pytest.fixture(scope="module")
def found():
    settings = DetectorSettings()
    return detect(movie(), None, settings), settings


def test_planted_events_are_found_where_and_when_they_were(found):
    detection, settings = found
    assert len(detection.events) == 2
    for (onset, row, col, _), (frame, r, c, z) in zip(EVENTS, detection.events):
        # A strong event raises the noise estimate at its own pixels, which flattens z into a plateau; its maximum
        # can lie anywhere on it, so the z maximum is checked to half the filter's width (the fitted centre is exact).
        assert abs(frame - onset) <= 3 and abs(r - row) <= 8 and abs(c - col) <= 8 and z > 15
    assert len(detection.sign_flipped) == 0 and len(detection.time_reversed) == 0


def test_dips_are_found_by_the_sign_flipped_search_only():
    detection = detect(movie(sign=-1.0), None, DetectorSettings())
    assert len(detection.events) == 0 and len(detection.sign_flipped) == 2


def test_searched_time_leaves_out_both_ends_the_template_and_the_end_trim(found):
    detection, settings = found
    frames = 899 - settings.first_frames - settings.last_frames
    shape, _ = template(settings)
    assert detection.searched_frames == frames - len(shape) + 1 - settings.frames(settings.end_trim_ms)


def test_an_onset_in_the_end_trim_is_not_counted():
    settings = DetectorSettings()
    late = [(740, 48, 48, 0.08)]  # onset in the last 0.32 s of the searched range (the last onset searched is 766)
    assert len(detect(movie(late), None, settings).events) == 0
    assert len(detect(movie(late), None, replace(settings, end_trim_ms=0.0)).events) == 1


def test_the_weaker_of_two_close_regions_of_opposite_sign_is_an_echo():
    settings = DetectorSettings()
    up = np.array([[100.0, 10, 10], [100.0, 60, 60]])
    down = np.array([[150.0, 12, 12]])
    kept, values = drop_echoes(up, np.array([9.0, 9.0]), down, np.array([12.0]), settings)
    assert kept.tolist() == [[100.0, 60, 60]]  # the first is close to a stronger dip
    kept, values = drop_echoes(down, np.array([12.0]), up, np.array([9.0, 9.0]), settings)
    assert len(kept) == 1  # the dip is the stronger: it stays
    assert len(drop_echoes(up, np.array([9.0, 9.0]), down, np.array([12.0]), replace(settings, echo_rule=False))[0]) == 2


def test_the_template_is_orthogonal_to_a_sloping_line(found):
    _, settings = found
    shape, before = template(settings)
    assert before == 21 and len(shape) == 21 + 123
    assert np.isclose((shape**2).sum(), 1) and abs(shape.sum()) < 1e-9 and abs((shape * np.arange(len(shape))).sum()) < 1e-6


def test_the_tissue_leaves_out_dark_blocks_and_the_electrode():
    settings = DetectorSettings()
    f0 = np.full((32, 32), 100.0)
    f0[:4, :4] = 10  # a dark block
    electrode = np.zeros((32, 32), bool)
    electrode[8:12, 0:2] = True  # half of a block: left out
    electrode[16:17, 0:4] = True  # a quarter of a block: kept
    mask = tissue_mask(f0, electrode, settings)
    assert not mask[:4, :4].any() and not mask[8:12, 0:4].any() and mask[16:20, 0:4].all()
    assert mask.sum() == 32 * 32 - 32


def test_event_measures_match_the_planted_events(found):
    detection, settings = found
    events = measure_events(detection, settings, (48, 48), None)
    for (onset, row, col, peak), e in zip(EVENTS, events):
        assert e["width"] == pytest.approx(SIGMA_PX * 16, rel=0.15)
        assert e["fitted peak"] == pytest.approx(peak * 100, rel=0.2)
        assert e["x"] == pytest.approx(col * 16, abs=16) and e["y"] == pytest.approx(row * 16, abs=16)
        assert e["size"] == pytest.approx(e["fitted peak"] * 2 * np.pi * (e["width"] / 1000) ** 2)
        assert 10 < e["rise 10-90"] < 60 and 90 < e["half-decay"] < 220
        assert e["local peak"] < e["fitted peak"]  # pooling dilutes the peak
        assert np.isnan(e["distance to the electrode"]) and np.isnan(e["electrode side"])
    assert set(events[0]) == set(EVENT_KEYS)


def test_time_course_of_a_known_trace():
    t = (np.arange(TRACE_BEFORE + 200) - TRACE_BEFORE) * FRAME_MS
    trace = 0.03 * kernel(t, 200.0, 12.0)
    found = time_course(trace, FRAME_MS)
    fine = np.linspace(0, 1000, 100001)
    shape = kernel(fine, 200.0, 12.0)
    peak_at = fine[np.argmax(shape)]  # 35.9 ms: the rise moves the peak
    rising = fine[: np.argmax(shape)]
    rise = rising[shape[: len(rising)] < 0.9].max() - rising[shape[: len(rising)] < 0.1].max()
    half_decay = fine[(fine > peak_at) & (shape < 0.5)].min() - peak_at  # 150.9 ms
    assert found["local peak"] == pytest.approx(3.0, rel=0.02)
    assert found["half-decay"] == pytest.approx(half_decay, abs=2 * FRAME_MS)
    assert found["rise 10-90"] == pytest.approx(rise, abs=2 * FRAME_MS)
    assert found["decay tau"] == pytest.approx(200, rel=0.1)
    assert found["half-width"] > found["half-decay"]


def test_recording_measures(found):
    detection, settings = found
    values = measure_recording(detection, settings)
    assert values["events"] == 2 and values["sign-flipped"] == 0 and values["time-reversed"] == 0
    assert values["searched time"] == pytest.approx(detection.searched_frames * FRAME_MS / 1000)
    assert values["rate"] == pytest.approx(2 / (values["searched time"] / 60))
    assert values["tissue area"] == pytest.approx(96 * 96 * 0.016**2)
    assert values["pixel noise"] == pytest.approx(2.0, rel=0.15)
    assert set(values) == set(RECORDING_KEYS)


def test_slice_summaries():
    settings = DetectorSettings()
    tissue = np.ones((128, 128), bool)
    recordings = [dict(events=3, **{"searched time": 6.0, "tissue area": 4.0, "sign-flipped": 1, "time-reversed": 0}),
                  dict(events=1, **{"searched time": 6.0, "tissue area": 4.0, "sign-flipped": 0, "time-reversed": 0})]
    base = {"distance to the release centre": 300.0, "electrode side": 1.0, "size": 0.5, "width": 150.0}
    events = [(0, dict(base, x=100.0, y=100.0, onset=1.0)), (0, dict(base, x=150.0, y=100.0, onset=1.5)),
              (0, dict(base, x=1500.0, y=1500.0, onset=5.0)), (1, dict(base, x=120.0, y=110.0, onset=2.0, width=250.0))]
    found = summarise_slice(recordings, events, settings, tissue, (64, 64), ["median", "max"], ["width"])
    assert found["events"] == 4 and found["rate"] == pytest.approx(4 / 0.2)
    assert found["rate above the sign-flip floor"] == pytest.approx(3 / 0.2) and found["sign-flipped share"] == 0.25
    assert found["share near the release centre"] == 1.0 and found["share on the electrode side"] == 1.0
    assert found["recurring sites"] == 1 and found["share at recurring sites"] == 0.75
    assert found["share together"] == 0.5  # 1.0 and 1.5 s are within 1 s of each other; 5.0 and 2.0 are alone
    assert found["clustering index"] < 0.5
    assert found["width median"] == 150.0 and found["width max"] == 250.0
    assert found["release per minute"] == pytest.approx(20 * 0.5)
    assert set(SLICE_KEYS) <= set(found)


def test_random_points_do_not_cluster():
    settings = DetectorSettings()
    rng = np.random.default_rng(3)
    points = rng.uniform(0, 128 * 16, (40, 2))
    assert 0.8 < clustering_index(points, np.ones((128, 128), bool), settings) < 1.2


def test_every_measure_is_described_in_full():
    fields_ = {"formula", "method", "empty", "meaning", "caveats"}
    for keys, details in ((EVENT_KEYS, EVENT_DETAILS), (RECORDING_KEYS, RECORDING_DETAILS), (SLICE_KEYS, SLICE_DETAILS)):
        assert set(details) == set(keys)
        for entry in details.values():
            assert set(entry) == fields_ and all(text.strip() for text in entry.values())


def test_every_setting_has_a_label_and_help():
    from dataclasses import fields

    for f in fields(DetectorSettings):
        assert f.metadata["label"] and f.metadata["help"] and f.metadata["group"]


def test_detector_file_round_trip_and_presets(tmp_path):
    detector = detector_v5()
    detector.settings.event_z = 7.5
    path = tmp_path / "mine.json"
    detector.save(path)
    assert Detector.load(path) == detector
    assert json.loads(path.read_text(encoding="utf-8"))["format"] == "EMA spontaneous detector"
    for make in library.PRESETS:
        assert Detector.load(library.PRESETS_FOLDER / library.file_name(make().name)) == make(), "run python -m ema.spontaneous.detector"


def test_searched_files_are_the_unstimulated_ones_without_skip_words(tmp_path):
    names = ["100uA.tif", "no1.tif", "No2.tif", "no3 red.tif", "hi1.tif", "no4_test.tif"]
    detector = detector_v5()
    detector.skip_words = ["red", "test"]
    assert [p.name for p in detector.searched_files([tmp_path / n for n in names])] == ["no1.tif", "No2.tif"]


def test_library_lists_built_in_then_saved(tmp_path):
    detector = detector_v5()
    detector.name = "Mine"
    library.save_in_library(detector, tmp_path)
    names = [e.name for e in library.entries(tmp_path)]
    assert names == ["Detector v5", "Mine"]
    assert library.is_taken("mine", tmp_path)


# ---------------------------------------------------------------------------
# The configurator
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def own_user_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "FILE", tmp_path / "user" / "settings.json")


def test_the_configurator_searches_an_example_recording(app, tmp_path):
    import tifffile

    from ema.spontaneous_configurator.window import SpontaneousConfiguratorWindow

    folder = tmp_path / "Slice 1" / "input output"
    folder.mkdir(parents=True)
    stack = movie()
    tifffile.imwrite(folder / "no1.tif", np.concatenate([stack[:1], stack]).clip(0, 65535).astype(np.uint16))
    window = SpontaneousConfiguratorWindow(user_folder=tmp_path / "detectors")
    assert window.library_box.count() == 1 and not window.delete_button.isEnabled()
    window.use_example_folder(folder, None)
    window.worker.wait()
    app.processEvents()
    assert window.status.text().startswith("no1.tif: <b>2 events</b>")
    assert window.table.rowCount() == 2
    window.form.inputs["event_z"].setValue(500.0)
    assert "press Search" in window.status.text() and window.unsaved
    window.form.inputs["good_fit_r2"].setValue(0.99)  # a measuring setting: measured again at once
    window.saved = window.detector.to_dict()
    window.close()
