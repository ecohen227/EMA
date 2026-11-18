"""Exclusions: which slices are left out of the tables, and why.

Each exclusion of a protocol (see protocol.Exclusion) makes one value per
slice from its recordings, such as the spread of B1, and compares it with the
same value of the other slices, or with a fixed limit. A slice that any
exclusion finds unusual is left out of both tables. The limits are always
worked out from every slice, before any is left out, so the order of the
exclusions does not matter.

Exclusions are applied when the tables are written, from the kept results,
so changing them measures nothing again. Nothing here needs the GUI.
"""

import math
import warnings
from dataclasses import dataclass

import numpy as np

from .protocol import (
    ABOVE,
    AMONG_ALL,
    BELOW,
    DEVIATIONS,
    HIGH_SIDE,
    INTERQUARTILE,
    LARGEST,
    LOW_SIDE,
    MEAN,
    MEDIAN,
    RANGE,
    SLICE_VALUES,
    SMALLEST,
    SPREAD_OF_LARGEST,
    SPREAD_OF_SMALLEST,
    VARIATION,
)

LEAST_SLICES = {INTERQUARTILE: 4, DEVIATIONS: 3}  # quartiles or a standard deviation of fewer slices mean little


@dataclass
class Verdict:
    """What one exclusion found for one slice."""

    slice: object  # an excel.Slice
    number: int  # of the exclusion, from 1
    value: float  # NaN when it could not be worked out
    low: float  # the slice is left out below `low` or above `high`; −inf and inf for no limit
    high: float
    left_out: bool
    why: str  # a sentence: why it is left out, or why it could not be tested; empty when it is kept


def slice_value(exclusion, recordings):
    """The one value an exclusion makes from a slice's recordings (each with .file, .condition and .values).
    Returns (value, why): NaN and why, such as 'it needs values of B1 in at least 2 recordings, and has 1.', when it
    cannot be worked out."""
    chosen = [recording for recording in recordings if exclusion.includes(recording.file, recording.condition)]
    if not any(exclusion.measure in recording.values for recording in chosen):
        return math.nan, (f"its recordings have no {exclusion.measure}." if chosen else "none of its recordings is one of "
                          "those the exclusion uses.")
    values = [float(r.values[exclusion.measure]) for r in chosen
              if r.values.get(exclusion.measure) is not None and math.isfinite(r.values[exclusion.measure])]
    least = SLICE_VALUES[exclusion.statistic][1]
    if len(values) < least:
        some = "a value" if least == 1 else f"values in at least {least} recordings"
        return math.nan, f"it needs {some} of {exclusion.measure}, and has {len(values)}."
    values = np.array(values)
    largest, smallest = values.max(), values.min()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        value = {
            SPREAD_OF_LARGEST: lambda: (largest - smallest) / largest * 100 if largest > 0 else math.nan,
            SPREAD_OF_SMALLEST: lambda: (largest - smallest) / smallest * 100 if smallest > 0 else math.nan,
            RANGE: lambda: largest - smallest,
            VARIATION: lambda: values.std(ddof=1) / abs(values.mean()) * 100 if values.mean() else math.nan,
            MEAN: values.mean,
            MEDIAN: lambda: np.median(values),
            SMALLEST: lambda: smallest,
            LARGEST: lambda: largest,
        }[exclusion.statistic]()
    if not math.isfinite(value):
        return math.nan, f"its value cannot be worked out (the values of {exclusion.measure} are 0 or below)."
    return float(value), ""


def limits(exclusion, values):
    """(low, high) for an exclusion, from the values of the slices it compares with. None if there are too few."""
    if exclusion.test == ABOVE:
        return -math.inf, exclusion.limit
    if exclusion.test == BELOW:
        return exclusion.limit, math.inf
    values = np.array([v for v in values if math.isfinite(v)])
    if len(values) < LEAST_SLICES[exclusion.test]:
        return None
    if exclusion.test == INTERQUARTILE:
        first, third = np.percentile(values, [25, 75])
        low, high = first - exclusion.factor * (third - first), third + exclusion.factor * (third - first)
    else:
        mean, deviation = values.mean(), values.std(ddof=1)
        low, high = mean - exclusion.factor * deviation, mean + exclusion.factor * deviation
    if exclusion.side == HIGH_SIDE:
        low = -math.inf
    elif exclusion.side == LOW_SIDE:
        high = math.inf
    return float(low), float(high)


def judge(protocol, found, group_of):
    """A Verdict for every slice of `found` and every exclusion of the protocol, slice by slice.

    `group_of(slice)` gives the name of a slice's group, for the exclusions
    that compare a slice with the slices of its group only.
    """
    units = {m.name: m.unit for m in protocol.recording_measures()}
    verdicts = []
    for number, exclusion in enumerate(protocol.exclusions, 1):
        worked_out = {item.key: slice_value(exclusion, item.result.recordings) for item in found}
        sets = {}
        for item in found:
            sets.setdefault(AMONG_ALL if exclusion.among == AMONG_ALL else group_of(item), []).append(item)
        unit = exclusion.unit(units.get(exclusion.measure, ""))
        for name, members in sets.items():
            bounds = limits(exclusion, [worked_out[item.key][0] for item in members])
            for item in members:
                value, why = worked_out[item.key]
                why = f"Not tested by exclusion {number}: {why}" if why else ""
                if bounds is None:
                    least = LEAST_SLICES[exclusion.test]
                    where = "slices" if exclusion.among == AMONG_ALL else f"slices in the group {name}"
                    verdicts.append(Verdict(item, number, value, math.nan, math.nan, False, why or (
                        f"Not tested by exclusion {number}: it needs a value in at least {least} {where}.")))
                    continue
                low, high = bounds
                left_out = math.isfinite(value) and not low <= value <= high
                if left_out:
                    side = f"above {_number(high)}" if value > high else f"below {_number(low)}"
                    why = (f"Left out by exclusion {number}: {exclusion.value_text(protocol.condition_label)} is "
                           f"{_number(value)}{_unit(unit)}, {side}{_unit(unit)} ({exclusion.test_text(unit)}).")
                verdicts.append(Verdict(item, number, value, low, high, left_out, why))
    order = {item.key: n for n, item in enumerate(found)}
    return sorted(verdicts, key=lambda v: (order[v.slice.key], v.number))


def left_out(verdicts):
    """The keys of the slices any exclusion leaves out."""
    return {verdict.slice.key for verdict in verdicts if verdict.left_out}


def _number(value):
    return f"{value:.4g}"


def _unit(unit):
    return "" if not unit or unit == "ratio" else (unit if unit == "%" else f" {unit}")
