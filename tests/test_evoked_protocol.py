"""Protocols: their checks, their files, editing them, and the library."""

import json
from datetime import datetime

import numpy as np
import pytest

from ema.evoked.presets import LIBRARY
from ema.evoked.presets import paired_pulse, paired_pulse_uncorrected, pulse_train
from ema.evoked.protocol import (
    AS_LISTED,
    BY_CONDITION,
    BY_FILES,
    EVERY,
    LISTED,
    NO_PARTNER,
    PER_RECORDING,
    RATIO,
    Protocol,
    ProtocolError,
    Recording,
    SliceMean,
    Window,
)
from ema.evoked.traces import find_partner, make_trace
from ema.recordings import recorded_after


def test_presets_are_complete_and_survive_a_file(tmp_path):
    for make in (paired_pulse, paired_pulse_uncorrected, pulse_train):
        protocol = make()
        assert protocol.problems() == []
        protocol.save(tmp_path / "p.json")
        assert Protocol.load(tmp_path / "p.json") == protocol


def test_shipped_preset_files_match_the_code():
    shipped = {entry.name: LIBRARY.load(entry.path) for entry in LIBRARY.entries() if entry.built_in}
    assert shipped == {"2P paired pulse": paired_pulse(), "2P paired pulse, uncorrected": paired_pulse_uncorrected(),
                       "11P pulse train": pulse_train()}


def test_file_is_readable(tmp_path):
    paired_pulse().save(tmp_path / "p.json")
    text = (tmp_path / "p.json").read_text(encoding="utf-8")
    assert '"B1": [81, 93]' in text and '"format": "EMA evoked protocol"' in text


def test_other_files_are_refused(tmp_path):
    (tmp_path / "x.json").write_text(json.dumps({"windows": {}}))
    with pytest.raises(ProtocolError, match="not an EMA evoked protocol"):
        Protocol.load(tmp_path / "x.json")
    (tmp_path / "y.json").write_text("{not json")
    with pytest.raises(ProtocolError, match="not a valid JSON"):
        Protocol.load(tmp_path / "y.json")
    damaged = paired_pulse().to_dict()
    del damaged["pulses"][0]["baseline"]
    with pytest.raises(ProtocolError, match="incomplete or damaged"):
        Protocol.from_dict(damaged)


@pytest.mark.parametrize(
    "change, problem",
    [
        (lambda p: setattr(p, "name", " "), "needs a name"),
        (lambda p: setattr(p.pulses[1], "name", "P1"), "P1 is used twice"),
        (lambda p: setattr(p.pulses[0], "baseline", "B9"), "B9, which does not exist"),
        (lambda p: setattr(p.pulses[0], "peak", Window(50, 40)), "peak window of P1 must start"),
        (lambda p: (setattr(p, "trace", RATIO), setattr(p, "partner", NO_PARTNER)), "needs an unstimulated partner"),
        (lambda p: setattr(p, "partner", AS_LISTED), "need a list of recordings"),
        (lambda p: setattr(p.comparisons[0], "pulse", "P7"), "P7, which is not a pulse"),
        (lambda p: setattr(p.fits[0], "length", 2), "at least 3 frames"),
        (lambda p: setattr(p.summary_means[0], "low", 500), "from low to high"),
        (lambda p: setattr(p.summary_means[0], "name", ""), "a name of its own"),
        (lambda p: p.summary_means.append(SliceMean("hi", BY_FILES)), "at least one file name"),
        (lambda p: p.pulses.clear(), "at least one pulse"),
    ],
)
def test_problems_are_found(change, problem):
    protocol = paired_pulse()
    change(protocol)
    assert any(problem in found for found in protocol.problems()), protocol.problems()


def test_listed_recordings_need_their_own_timing():
    protocol = pulse_train()
    del protocol.recordings[2].baselines["BLPre11"]
    protocol.recordings[1].unstimulated = ""
    found = protocol.problems()
    assert "BLPre11 of hi3.tif is not set." in found and "hi2.tif needs an unstimulated partner." in found


def test_rename_follows_every_reference():
    protocol = pulse_train()
    protocol.rename("P11", "Recovery")
    protocol.rename("BL", "Rest")
    assert protocol.pulse("Recovery").per_recording and all("Recovery" in r.pulses for r in protocol.recordings)
    assert {c.pulse for c in protocol.comparisons if c.name.startswith("P11")} == {"Recovery"}
    assert protocol.pulse("P1").baseline == "Rest" and protocol.problems() == []


def test_per_recording_timing_can_be_switched_on_and_off():
    protocol = paired_pulse()
    protocol.selection = LISTED
    protocol.recordings = [__import__("ema.evoked.protocol", fromlist=["Recording"]).Recording("200uA.tif")]
    p2 = protocol.pulse("P2")
    protocol.set_pulse_per_recording(p2, True)
    protocol.set_baseline_per_recording("B2", True)
    assert protocol.baselines["B2"] == PER_RECORDING and protocol.recordings[0].baselines["B2"] == Window(904, 925)
    assert protocol.pulse_timing(p2, protocol.recordings[0]) == (928, Window(904, 1125))
    assert protocol.problems() == []

    protocol.set_pulse_per_recording(p2, False)
    protocol.set_baseline_per_recording("B2", False)
    assert (p2.stimulus, p2.peak, protocol.baselines["B2"]) == (928, Window(904, 1125), Window(904, 925))
    assert protocol.recordings[0].pulses == {} and protocol.recordings[0].baselines == {}


def test_place_pulses_builds_a_regular_train():
    protocol = pulse_train()
    protocol.place_pulses(first_stimulus=100, count=5, interval_frames=20.6, peak_frames=15, baseline_frames=10, shared_baseline=True)
    names = [p.name for p in protocol.pulses]
    assert names == ["P1", "P2", "P3", "P4", "P5", "P11"]  # the per-recording recovery pulse is kept
    assert [p.stimulus for p in protocol.pulses[:5]] == [100, 121, 141, 162, 182]
    assert protocol.pulse("P3").peak == Window(141, 156) and protocol.baselines["BL"] == Window(90, 100)
    assert protocol.baselines["BLPre11"] == PER_RECORDING

    protocol.place_pulses(100, 12, 20, 15, 10, shared_baseline=False)
    assert protocol.pulse("P11").per_recording is False and protocol.pulse("P13").per_recording is True
    assert protocol.pulse("P12").baseline == "B12" and protocol.baselines["B12"] == Window(310, 320)


def test_add_pulse_continues_the_train():
    protocol = paired_pulse()  # each pulse has its own baseline: so does the new one
    p3 = protocol.add_pulse()
    assert (p3.name, p3.baseline, p3.peak, p3.stimulus) == ("P3", "B3", Window(1729, 1950), 1753)
    assert protocol.baselines["B3"] == Window(1729, 1750)

    train = pulse_train()  # train pulses share BL: so does the new one
    p12 = train.add_pulse()
    assert (p12.name, p12.baseline, p12.stimulus) == ("P12", "BL", 289 + 21)


def test_measures_follow_the_settings():
    protocol = paired_pulse()
    protocol.kinetic_measures = ["half-width"]
    names = [m.name for m in protocol.measures()]
    assert "P1 half-width" in names and "P1 half-width mean 100-400" in names and "B2 spread" in names
    assert names.index("P2 response") < names.index("PPR") < names.index("Tau") < names.index("B1 min")
    assert "P1 peak" not in names and "P1" not in names  # the peaks are not written unless chosen
    protocol.write_peaks = True
    names = [m.name for m in protocol.measures()]
    assert names[names.index("P1 response") - 1] == "P1 peak" and "P1 peak mean 100-400" in names


def test_protocols_saved_before_the_peak_switch_keep_their_peaks():
    data = paired_pulse().to_dict()
    del data["write_peaks"]
    assert Protocol.from_dict(data).write_peaks


def test_every_mode_skips_unstimulated_red_and_test(tmp_path):
    names = ["50uA.tif", "300uA.tif", "no1.tif", "No2.tif", "hi1 red.tif", "hi1_red.tif", "hired.tif",
             "test stim 200uA.tif", "200uA test pulse.tif", "test-1.tif", "contest.tif"]
    paths = [tmp_path / name for name in names]
    assert [p.name for p in paired_pulse().measured_files(paths)] == ["50uA.tif", "300uA.tif", "hired.tif", "contest.tif"]


# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------


def test_library_lists_built_in_first_then_saved(tmp_path):
    for name in ("Zeta", "3P triple", "alpha"):
        protocol = paired_pulse()
        protocol.name = name
        LIBRARY.in_folder(tmp_path).save(protocol)
    (tmp_path / "broken.json").write_text("{")
    labels = [entry.label for entry in LIBRARY.in_folder(tmp_path).entries()]
    assert labels == ["2P paired pulse  (built in)", "2P paired pulse, uncorrected  (built in)", "11P pulse train  (built in)",
                      "3P triple", "alpha", "Zeta"]


def test_saving_under_a_new_name_replaces_the_old_file(tmp_path):
    protocol = paired_pulse()
    protocol.name = "Mine"
    first = LIBRARY.in_folder(tmp_path).save(protocol)
    protocol.name = "Mine: renamed?"
    second = LIBRARY.in_folder(tmp_path).save(protocol, replacing=first)
    assert not first.exists() and second.name == "Mine- renamed-.json"
    assert LIBRARY.in_folder(tmp_path).is_taken("mine: RENAMED?") and not LIBRARY.in_folder(tmp_path).is_taken("mine")
    assert LIBRARY.in_folder(tmp_path).is_taken("2P paired pulse")


def test_built_in_protocols_cannot_be_deleted():
    entry = LIBRARY.entries()[0]
    with pytest.raises(ValueError, match="cannot be deleted"):
        LIBRARY.delete(entry)


def test_every_mode_cannot_keep_per_recording_timing():
    protocol = pulse_train()
    protocol.trace = "brightness"
    protocol.selection = EVERY
    assert any("needs a list of recordings" in p for p in protocol.problems())


# ---------------------------------------------------------------------------
# Unstimulated partners
# ---------------------------------------------------------------------------


def test_protocols_written_before_partners_keep_their_meaning():
    for make, partner in ((paired_pulse, NO_PARTNER), (pulse_train, AS_LISTED)):
        data = make().to_dict()
        del data["recordings"]["unstimulated_partner"]
        assert Protocol.from_dict(data).partner == partner


def test_the_partner_is_the_unstimulated_recording_made_right_after(tmp_path):
    files = {"50uA.tif": "10:00", "no1.tif": "10:01", "100uA.tif": "10:02", "no2.tif": "10:03", "200uA.tif": "10:04",
             "no3 red.tif": "10:05"}
    paths = [tmp_path / name for name in files]
    times = {path: datetime.strptime(f"2025-12-05 {files[path.name]}", "%Y-%m-%d %H:%M") for path in paths}
    protocol = paired_pulse()
    partners = [find_partner(protocol, path, paths, times=times)[0].name for path in protocol.measured_files(paths)]
    assert partners == ["no1.tif", "no2.tif", "no2.tif"]  # 200uA.tif was the last: the one before it ('red' is skipped)
    listed = Recording("200uA.tif", "no1.tif")
    assert find_partner(protocol, paths[4], paths, listed, times)[0].name == "no1.tif"  # a named partner wins
    assert find_partner(paired_pulse_uncorrected(), paths[0], paths, times=times) == (None, "")


def test_a_recording_without_a_time_stamp_has_no_partner(tmp_path):
    times = {tmp_path / "50uA.tif": None, tmp_path / "no1.tif": datetime(2025, 12, 5)}
    partner, reason = recorded_after(tmp_path / "50uA.tif", [tmp_path / "no1.tif"], times)
    assert partner is None and "has no time stamp" in reason


def test_the_correction_matches_ema_2_divide_background():
    rng = np.random.default_rng(0)
    frames = np.arange(1649)
    background = 600 * np.exp(-frames / 20000) + rng.normal(0, 2, frames.size)
    stimulated = background * (1 + 0.5 * np.exp(-np.clip(frames - 103, 0, None) / 40) * (frames >= 103))
    protocol = paired_pulse()
    corrected = make_trace(protocol, stimulated, background)
    expected = stimulated * (background[81:93].mean() / background)  # EMA 2.4, divide_background with window B1
    assert np.array_equal(corrected, expected)
    assert make_trace(paired_pulse_uncorrected(), stimulated) is stimulated
    assert np.array_equal(make_trace(pulse_train(), stimulated, background), (stimulated / background - 1) * 100)
    with pytest.raises(ValueError, match="needs an unstimulated partner"):
        make_trace(protocol, stimulated)


def test_fits_across_conditions_survive_a_file(tmp_path):
    from ema.evoked.protocol import SATURATION, ConditionFit

    protocol = pulse_train()
    protocol.condition_fits = [ConditionFit("Recovery", "P11/P1", plateau=100.0), ConditionFit("IO", "P1 response", SATURATION)]
    protocol.save(tmp_path / "p.json")
    assert Protocol.load(tmp_path / "p.json") == protocol
    protocol.condition_fits[1].measure = "P1 width"
    assert any("P1 width, which is not measured per recording" in p for p in protocol.problems())


def test_a_fit_across_conditions_of_a_peak_saved_under_the_pulse_name_still_loads():
    from ema.evoked.protocol import SATURATION, ConditionFit

    saved = paired_pulse()
    saved.condition_fits = [ConditionFit("IO", "P1 peak", SATURATION)]
    data = saved.to_dict()
    data["slice_summary"]["condition_fits"][0]["measure"] = "P1"
    loaded = Protocol.from_dict(data)
    assert loaded.condition_fits[0].measure == "P1 peak" and not loaded.problems()


def test_every_measure_is_described_in_full():
    from ema.evoked.measure_details import BASIC, KINETIC_DETAILS, NEAR_TO_FAR_DETAILS, SLICE, SPATIAL_DETAILS
    from ema.evoked.catalogue import KINETIC_KEYS, SPATIAL_KEYS

    required = {"formula", "method", "empty", "meaning", "caveats"}
    assert set(KINETIC_DETAILS) == set(KINETIC_KEYS) and set(SPATIAL_DETAILS) == set(SPATIAL_KEYS)
    for details in [*KINETIC_DETAILS.values(), *SPATIAL_DETAILS.values(), NEAR_TO_FAR_DETAILS]:
        assert required <= set(details) <= required | {"example"}
        assert all(text.strip() for text in details.values())
    # every kind of measure a protocol produces besides the catalogue, each with a worked example
    kinds = {"baseline", "peak", "response brightness", "response ratio", "comparison", "single fit", "double fit"}
    assert {entry["key"] for entry in BASIC} == kinds
    assert {entry["key"] for entry in SLICE} == {"statistics", "recordings mean", "baseline spread", "recovery fit", "saturation fit"}
    for entry in BASIC + SLICE:
        assert required | {"key", "title", "name", "unit", "definition", "example"} == set(entry)
        assert all(text.strip() for text in entry.values())


def test_a_mean_over_recordings_takes_a_condition_range_or_file_names():
    from ema.evoked.protocol import file_patterns

    hi = SliceMean("hi", BY_FILES, files=["hi*"])
    assert hi.includes("hi1.tif", None) and hi.includes("HI4.TIF", None) and not hi.includes("no1.tif", None)
    listed = SliceMean("", BY_FILES, files=file_patterns("hi1, hi3.tif,, "))
    assert listed.files == ["hi1", "hi3.tif"]
    assert [listed.includes(f, None) for f in ("hi1.tif", "hi2.tif", "hi3.tif", "hi10.tif")] == [True, False, True, False]
    assert SliceMean("", BY_FILES, files=["hi[1-4]"]).includes("hi4.tif", None)
    assert (hi.automatic_name(), listed.automatic_name()) == ("hi", "hi1+hi3")
    in_range = SliceMean("100-400", BY_CONDITION, 100.0, 400.0)
    assert in_range.automatic_name() == "100-400"
    assert in_range.includes("hi1.tif", 400.0) and not in_range.includes("50uA.tif", 50.0) and not in_range.includes("hi1.tif", None)


def test_means_over_recordings_are_saved_and_give_their_own_columns():
    protocol = paired_pulse()
    protocol.summary_means.append(SliceMean("hi", BY_FILES, files=["hi*"]))
    loaded = Protocol.from_dict(json.loads(json.dumps(protocol.to_dict())))
    assert loaded.summary_means == protocol.summary_means and not loaded.problems()
    columns = {m.name: m for m in loaded.measures() if m.per == "slice"}
    assert "P1 response mean 100-400" in columns and "P1 response mean hi" in columns
    assert columns["P1 response mean hi"].explanation.endswith("whose file name matches hi*.")


def test_a_protocol_saved_with_a_condition_range_has_that_mean():
    data = paired_pulse().to_dict()
    del data["slice_summary"]["means"]
    data["slice_summary"]["condition_range"] = [50, 300]
    assert Protocol.from_dict(data).summary_means == [SliceMean("50-300", BY_CONDITION, 50.0, 300.0)]
    data["slice_summary"]["condition_range"] = None
    assert Protocol.from_dict(data).summary_means == []
