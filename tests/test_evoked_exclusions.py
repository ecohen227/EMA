"""Exclusions: slices left out of both tables when one value made from their recordings is unusual."""

import math
from types import SimpleNamespace

import pytest

from ema.evoked.exclusions import judge, left_out, limits, slice_value
from ema.evoked.presets import paired_pulse
from ema.evoked.protocol import (
    ABOVE,
    AMONG_GROUP,
    BELOW,
    BY_CONDITION,
    BY_FILES,
    DEVIATIONS,
    HIGH_SIDE,
    MEAN,
    RANGE,
    SPREAD_OF_SMALLEST,
    VARIATION,
    Exclusion,
    Protocol,
)


def recording(b1, file="200uA.tif", condition=200.0, **values):
    return SimpleNamespace(file=file, condition=condition, values={"B1": b1, **values})


def a_slice(name, b1s, group=("WT",)):
    recordings = [recording(b1, f"{100 * n}uA.tif", 100.0 * n) for n, b1 in enumerate(b1s, 1)]
    return SimpleNamespace(key=name, result=SimpleNamespace(name=name, recordings=recordings), group=group)


# Seven steady slices and one whose baseline fell by 40 % between its recordings
STEADY = [[100, 97, 98], [200, 196], [150, 147, 145], [120, 118, 117], [90, 88], [110, 106, 108], [130, 128, 127]]
SLICES = [a_slice(f"slice {n}", b1s) for n, b1s in enumerate(STEADY, 1)] + [a_slice("drifting", [100, 70, 60])]


def protocol_with(*exclusions):
    protocol = paired_pulse()
    protocol.exclusions = list(exclusions)
    return protocol


def test_the_spread_of_b1_is_relative_to_the_largest():
    value, why = slice_value(Exclusion("B1"), SLICES[-1].result.recordings)
    assert value == pytest.approx(40.0) and not why
    assert slice_value(Exclusion("B1", SPREAD_OF_SMALLEST), SLICES[-1].result.recordings)[0] == pytest.approx(40 / 60 * 100)
    assert slice_value(Exclusion("B1", RANGE), SLICES[-1].result.recordings)[0] == 40
    assert slice_value(Exclusion("B1", MEAN), SLICES[-1].result.recordings)[0] == pytest.approx(230 / 3)
    assert slice_value(Exclusion("B1", VARIATION), SLICES[-1].result.recordings)[0] == pytest.approx(21.0 / (230 / 3) * 100, rel=0.01)


def test_a_slice_with_one_recording_has_no_spread():
    value, why = slice_value(Exclusion("B1"), [recording(100)])
    assert math.isnan(value) and "at least 2 recordings" in why
    assert slice_value(Exclusion("B1", MEAN), [recording(100)])[0] == 100  # a mean needs only one


def test_only_the_chosen_recordings_count():
    recordings = [recording(100, "hi1.tif", None), recording(50, "hi2.tif", None), recording(10, "lo1.tif", None)]
    assert slice_value(Exclusion("B1", RANGE, BY_FILES, files=["hi*"]), recordings)[0] == 50
    recordings = [recording(100, "100uA.tif", 100), recording(80, "200uA.tif", 200), recording(10, "500uA.tif", 500)]
    assert slice_value(Exclusion("B1", RANGE, BY_CONDITION, 100, 400), recordings)[0] == 20


def test_the_interquartile_fences():
    exclusion = Exclusion("B1", factor=1.5)
    low, high = limits(exclusion, [1, 2, 3, 4, 5, 6, 7, 8, math.nan])
    assert (low, high) == (2.75 - 1.5 * 3.5, 6.25 + 1.5 * 3.5)
    assert limits(Exclusion("B1", factor=0), [1, 2, 3, 4, 5]) == (2, 4)  # k = 0: outside the interquartile range itself
    assert limits(Exclusion("B1", side=HIGH_SIDE), [1, 2, 3, 4, 5])[0] == -math.inf
    assert limits(exclusion, [1, 2, 3]) is None  # too few slices for quartiles
    assert limits(Exclusion("B1", test=DEVIATIONS, factor=2), [1, 2, 3]) == pytest.approx((0, 4))
    assert limits(Exclusion("B1", test=ABOVE, limit=15), []) == (-math.inf, 15)
    assert limits(Exclusion("B1", test=BELOW, limit=15), []) == (15, math.inf)


def test_the_drifting_slice_is_left_out():
    verdicts = judge(protocol_with(Exclusion("B1")), SLICES, lambda item: "WT")
    assert left_out(verdicts) == {"drifting"}
    out = next(v for v in verdicts if v.left_out)
    assert out.value == pytest.approx(40) and out.high < 40
    assert out.why.startswith("Left out by exclusion 1: B1: (largest − smallest) ÷ largest × 100 over its recordings is 40%")
    assert "above Q3 + 1.5 × IQR" in out.why


def test_every_exclusion_judges_every_slice_and_any_leaves_it_out():
    protocol = protocol_with(Exclusion("B1", test=ABOVE, limit=30), Exclusion("B1", MEAN, test=BELOW, limit=95))
    verdicts = judge(protocol, SLICES, lambda item: "WT")
    assert len(verdicts) == 2 * len(SLICES)
    assert left_out(verdicts) == {"drifting", "slice 5"}  # slice 5: mean B1 89


def test_among_its_group_the_limits_are_worked_out_per_group():
    slices = [a_slice(f"WT {n}", [100, 99]) for n in range(4)] + [a_slice(f"HET {n}", [100, 80], ("HET",)) for n in range(4)]
    slices.append(a_slice("HET drifting", [100, 60], ("HET",)))
    group_of = lambda item: item.group[0]  # noqa: E731
    among_all = judge(protocol_with(Exclusion("B1", side=HIGH_SIDE)), slices, group_of)
    assert left_out(among_all) == set()  # the HET slices all drift more than the WT ones: the quartiles are wide
    per_group = judge(protocol_with(Exclusion("B1", side=HIGH_SIDE, among=AMONG_GROUP)), slices, group_of)
    assert left_out(per_group) == {"HET drifting"}


def test_too_few_slices_are_not_tested():
    verdicts = judge(protocol_with(Exclusion("B1")), SLICES[:3], lambda item: "WT")
    assert not left_out(verdicts)
    assert all("needs a value in at least 4 slices" in v.why for v in verdicts)


def test_exclusions_are_saved_and_read_back():
    protocol = protocol_with(Exclusion("B1"), Exclusion("P1 response", MEAN, BY_FILES, files=["hi*"], test=ABOVE, limit=12.5),
                             Exclusion("P1 peak", RANGE, BY_CONDITION, 100, 400, test=DEVIATIONS, factor=2,
                                       side=HIGH_SIDE, among=AMONG_GROUP))
    assert Protocol.from_dict(protocol.to_dict()).exclusions == protocol.exclusions
    assert protocol.to_dict()["exclusions"][0]["recordings"] == "all"
    assert not protocol.problems()  # peaks are measured even when they are not written, so they can be used


def test_exclusions_follow_a_rename_and_report_problems():
    protocol = protocol_with(Exclusion("B1"), Exclusion("P1 response", MEAN))
    protocol.rename("P1", "First")
    assert protocol.exclusions[1].measure == "First response"
    protocol.exclusions.append(Exclusion("nothing", by=BY_FILES))
    problems = " ".join(protocol.problems())
    assert "Exclusion 3 uses nothing, which is not measured per recording" in problems
    assert "Exclusion 3 needs at least one file name" in problems
