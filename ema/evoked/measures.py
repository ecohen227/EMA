"""Measuring one trace with a protocol.

The arithmetic follows the definitions shown in the configurator (see
`Protocol.measures`), in the same order of operations as the earlier EMA
programs, so that their numbers are reproduced exactly. Nothing here needs
the GUI.
"""

import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit

from .kinetics import kinetics
from .protocol import BRIGHTNESS, DOUBLE, PERCENT_SCALE, SATURATION


@dataclass
class Measurement:
    """The numbers measured on one trace, and where they came from (for drawing them)."""

    values: dict = field(default_factory=dict)  # measure name -> number
    levels: dict = field(default_factory=dict)  # baseline name -> (window, mean)
    peaks: dict = field(default_factory=dict)  # pulse name -> (frame of the maximum, maximum)
    fits: dict = field(default_factory=dict)  # fit name -> (first frame, fitted curve), or None if it failed
    fit_frames: dict = field(default_factory=dict)  # fit name -> (first frame, last frame + 1) it covers
    problems: list = field(default_factory=list)  # what could not be measured, as sentences


def exponential(x, a, tau, c):
    return a * np.exp(-x / tau) + c


def double_exponential(x, a1, tau1, a2, tau2, c):
    return a1 * np.exp(-x / tau1) + a2 * np.exp(-x / tau2) + c


def recovery(x, start, plateau, tau):
    return plateau - (plateau - start) * np.exp(-x / tau)


def hill(x, top, half, steepness):
    x = np.clip(x, 0, None)
    return top * x**steepness / (half**steepness + x**steepness)


def measure(protocol, trace, recording=None):
    """Measure a trace (one value per frame) with a protocol.

    `recording` is the listed recording the trace belongs to, which gives the
    timing of per-recording windows. Values that cannot be measured are NaN,
    and `problems` says why.
    """
    result = Measurement()
    trace = np.asarray(trace, dtype=float)

    for name in protocol.baselines:
        window = protocol.baseline_window(name, recording)
        if _usable(window, trace, name, result):
            level = trace[window.start : window.end].mean()
            result.levels[name] = (window, level)
            result.values[name] = level
        else:
            result.values[name] = np.nan

    responses, timings = {}, {}
    for pulse in protocol.pulses:
        stimulus, window = timings[pulse.name] = protocol.pulse_timing(pulse, recording)
        baseline = result.values.get(pulse.baseline, np.nan)
        if _usable(window, trace, pulse.name, result):
            segment = trace[window.start : window.end]
            frame = window.start + int(np.argmax(segment))
            peak = segment.max()
            result.peaks[pulse.name] = (frame, peak)
        else:
            peak = np.nan
        responses[pulse.name] = response(protocol, peak, baseline)
        result.values[pulse.name] = peak
        result.values[f"{pulse.name} response"] = responses[pulse.name]

    if protocol.kinetic_measures:
        for name in protocol.kinetic_pulse_names():
            pulse = protocol.pulse(name)
            stimulus, window = timings[name]
            baseline_window = protocol.baseline_window(pulse.baseline, recording)
            found = kinetics(protocol, trace, result.values.get(pulse.baseline, np.nan), baseline_window, stimulus, window)
            for key, value in found.items():
                result.values[f"{name} {key}"] = value

    for comparison in protocol.comparisons:
        result.values[comparison.name] = compare(responses.get(comparison.pulse, np.nan), responses.get(comparison.relative_to, np.nan), comparison.scale)

    for fit in protocol.fits:
        frames = fit_frames(protocol, fit, trace, recording)
        if frames is not None:
            result.fit_frames[fit.name] = frames
        values, curve = fit_decay(protocol, fit, trace, recording)
        for name, value in zip(fit.measure_names(), values):
            result.values[name] = value
        result.fits[fit.name] = curve
        if curve is None:
            result.problems.append(f"The fit {fit.name} did not converge.")
    return result


def _usable(window, trace, name, result):
    if window is None:
        result.problems.append(f"{name}: the window is not set.")
        return False
    if window.start >= len(trace):
        result.problems.append(f"{name}: the window starts after the end of the recording ({len(trace)} frames).")
        return False
    return True


def response(protocol, peak, baseline):
    """The response of a pulse: relative change of brightness, or rise of a stimulated ÷ unstimulated trace."""
    if protocol.trace == BRIGHTNESS:
        return peak / baseline * 100 - 100
    return peak - baseline if baseline != 0 else np.nan


def compare(response, relative_to, scale):
    if relative_to == 0 or not np.isfinite(relative_to):
        return np.nan
    return response / relative_to * 100 if scale == PERCENT_SCALE else response / relative_to


# ---------------------------------------------------------------------------
# Exponential fits
# ---------------------------------------------------------------------------


def fit_frames(protocol, fit, trace, recording=None):
    """First and last + 1 frame of a fit in a trace, or None if its pulse cannot be found."""
    start = fit.start
    if fit.after is not None:
        _, window = protocol.pulse_timing(protocol.pulse(fit.after), recording)
        if window is None or window.start >= len(trace):
            return None
        start += window.start + int(np.argmax(trace[window.start : window.end]))
    return start, min(start + fit.length, len(trace))


def fit_decay(protocol, fit, trace, recording=None):
    """The fit's values (τ in ms; for a double fit τ fast, τ slow and the fast fraction) and (first frame, fitted curve).

    NaN values and None when the fit fails.
    """
    failed = [np.nan] * len(fit.measure_names())
    frames = fit_frames(protocol, fit, trace, recording)
    if frames is None or frames[1] - frames[0] < (6 if fit.kind == DOUBLE else 3):
        return failed, None
    first, last = frames
    y = trace[first:last]
    x = np.arange(last - first)
    dt = protocol.sampling_interval_ms
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if fit.kind == DOUBLE:
                size = y[0] - y[-1]
                start = [0.6 * size, 80 / dt, 0.4 * size, 600 / dt, y[-1]]
                limits = ([0, 0.2, 0, 0.2, -np.inf], [np.inf, 1e6, np.inf, 1e6, np.inf])
                p, _ = curve_fit(double_exponential, x, y, p0=start, bounds=limits, maxfev=20000)
                (a1, t1, a2, t2, c) = p if p[1] <= p[3] else (p[2], p[3], p[0], p[1], p[4])
                return [t1 * dt, t2 * dt, a1 / (a1 + a2) if a1 + a2 > 0 else np.nan], (first, double_exponential(x, *p))
            parameters, _ = curve_fit(exponential, x, y, p0=[y.max() - y.min(), 50, y.min()])
    except (RuntimeError, ValueError, TypeError):
        return failed, None
    tau = parameters[1]
    return [tau * dt if np.isfinite(tau) else np.nan], (first, exponential(x, *parameters))


# ---------------------------------------------------------------------------
# A slice: several recordings
# ---------------------------------------------------------------------------


def summarise(protocol, rows):
    """The slice measures from the per-recording values of its recordings.

    `rows` is a list of (condition, values) with one entry per recording, as
    made by `measure`. The result maps each slice measure to its value.
    """
    names = [m.name for m in protocol.measures() if m.per == "recording"]
    conditions = [condition for condition, _ in rows]
    summary = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for name in names:
            values = [row.get(name, np.nan) for _, row in rows]
            for statistic in protocol.summary_statistics:
                summary[f"{name} {statistic}"] = {"min": np.nanmin, "max": np.nanmax, "mean": np.nanmean}[statistic](values)
            if protocol.summary_condition_range:
                low, high = protocol.summary_condition_range
                inside = [v for v, c in zip(values, conditions) if c is not None and low <= c <= high]
                summary[f"{name} mean {low:g}-{high:g}"] = np.nanmean(inside) if inside else np.nan
        if protocol.summary_baseline_spread:
            for name in protocol.baselines:
                values = [row.get(name, np.nan) for _, row in rows]
                summary[f"{name} spread"] = (np.max(values) - np.min(values)) / np.min(values) * 100
        for fit in protocol.condition_fits:
            summary.update(fit_across_conditions(fit, conditions, [row.get(fit.measure, np.nan) for _, row in rows]))
    return summary


def fit_across_conditions(fit, conditions, values):
    """The parameters of a ConditionFit, by name, from the recordings' conditions and values. NaN if it cannot be fitted.

    A fit needs more recordings (with different conditions) than it has free
    parameters. Its result is kept only when it lies inside the bounds below,
    so that a curve that only extrapolates far beyond the data gives nothing:
    τ from 1/1000 to 10 times the largest condition, the half-max up to 10
    times the largest condition, the steepness from 0.3 to 20.
    """
    found = dict.fromkeys(fit.measure_names(), np.nan)
    x = np.array([np.nan if c is None else c for c in conditions], float)
    y = np.array(values, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if not x.size or x.max() <= 0:
        return found
    largest, distinct = x.max(), len(np.unique(x))
    inside = lambda value, low, high: low * 1.001 < value < high * 0.999  # noqa: E731  not stuck at a bound
    try:
        if fit.model == SATURATION:
            if distinct < 4 or (x < 0).any():
                return found
            (top, half, steepness), _ = curve_fit(hill, x, y, p0=[y.max(), np.median(x[x > 0]), 2.0],
                                                  bounds=([0, largest / 1000, 0.3], [np.inf, 10 * largest, 20]), maxfev=20000)
            if inside(half, largest / 1000, 10 * largest) and inside(steepness, 0.3, 20):
                found.update({f"{fit.name} half-max": half, f"{fit.name} max": top, f"{fit.name} steepness": steepness})
            return found
        tau0, start0 = np.median(x), y[np.argmin(x)]
        bounds_tau = (largest / 1000, 10 * largest)
        if fit.plateau is None:
            if distinct < 4:
                return found
            (start, plateau, tau), _ = curve_fit(recovery, x, y, p0=[start0, y[np.argmax(x)], tau0],
                                                 bounds=([-np.inf, -np.inf, bounds_tau[0]], [np.inf, np.inf, bounds_tau[1]]), maxfev=20000)
        else:
            if distinct < 3:
                return found
            plateau = fit.plateau
            (start, tau), _ = curve_fit(lambda x_, s, t: recovery(x_, s, plateau, t), x, y, p0=[start0, tau0],
                                        bounds=([-np.inf, bounds_tau[0]], [np.inf, bounds_tau[1]]), maxfev=20000)
        if inside(tau, *bounds_tau):
            found.update({f"{fit.name} time constant": tau, f"{fit.name} start": start})
            if fit.plateau is None:
                found[f"{fit.name} plateau"] = plateau
    except (RuntimeError, ValueError):
        pass
    return found
