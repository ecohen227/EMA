"""Kinetic measures of one pulse: the time course of its response.

The response is the trace as a change from the pulse's baseline, in percent,
smoothed with a running mean. Only the stretch from the stimulus (or the start
of the peak window, if that is earlier) to the end of the peak window is
used. Times at which the response crosses a level are interpolated between
frames; a level that is not crossed inside the stretch gives NaN.
"""

import numpy as np
from scipy import ndimage

from .protocol import BRIGHTNESS


def response_trace(protocol, trace, baseline):
    """The trace as a response in percent: relative to the baseline for brightness, minus it for ratios."""
    if protocol.trace == BRIGHTNESS:
        return (trace / baseline - 1) * 100
    return trace - baseline


def smoothed(protocol, response):
    frames = protocol.kinetic_smoothing_frames
    return ndimage.uniform_filter1d(response, frames) if frames > 1 else response


def kinetics(protocol, trace, baseline, baseline_window, stimulus, window):
    """Every kinetic measure chosen in the protocol, for one pulse."""
    found = dict.fromkeys(protocol.kinetic_measures, np.nan)
    if window is None or window.start >= len(trace) or not np.isfinite(baseline) or baseline == 0:
        return found
    dt = protocol.sampling_interval_ms
    raw = response_trace(protocol, trace, baseline)
    smooth = smoothed(protocol, raw)
    first = window.start if stimulus is None else min(stimulus, window.start)
    last = min(window.end, len(trace)) - 1
    peak = window.start + int(np.argmax(smooth[window.start : last + 1]))
    height = smooth[peak]
    if height <= 0:
        return found

    def before(fraction):
        return crossing(smooth, height * fraction, peak, first, -1)

    def after(fraction):
        return crossing(smooth, height * fraction, peak, last, +1)

    def since_stimulus(frame):
        return (frame - stimulus) * dt if stimulus is not None else np.nan

    rising, falling = smooth[first : peak + 1], smooth[peak : last + 1]
    noise = np.nan
    if baseline_window is not None and baseline_window.end - baseline_window.start >= 2:
        noise = raw[baseline_window.start : baseline_window.end].std()
    values = {
        "time to peak": since_stimulus(peak + vertex(smooth, peak, window.start, last)),
        "onset": since_stimulus(before(0.2)),
        "rise 10-90": (before(0.9) - before(0.1)) * dt,
        "rise 20-80": (before(0.8) - before(0.2)) * dt,
        "max rise slope": np.max(np.diff(rising)) / (dt / 1000) if len(rising) > 1 else np.nan,
        "max decay slope": -np.min(np.diff(falling)) / (dt / 1000) if len(falling) > 1 else np.nan,
        "half-width": (after(0.5) - before(0.5)) * dt,
        "half-decay": (after(0.5) - peak) * dt,
        "1/e decay": (after(np.exp(-1)) - peak) * dt,
        "area": raw[first : last + 1].sum() * dt / 1000,
        "signal-to-noise": height / noise if noise and np.isfinite(noise) else np.nan,
    }
    return {name: values[name] for name in protocol.kinetic_measures}


def vertex(trace, peak, first, last):
    """Where, between frames, the top of the parabola through the peak frame and its two neighbours lies: an offset
    from the peak frame between −0.5 and 0.5. 0 when the peak is at either end of [first, last]."""
    if peak <= first or peak >= last:
        return 0.0
    before, top, after = trace[peak - 1], trace[peak], trace[peak + 1]
    curvature = before - 2 * top + after
    return float(np.clip(0.5 * (before - after) / curvature, -0.5, 0.5)) if curvature < 0 else 0.0


def crossing(trace, level, peak, limit, step):
    """The (interpolated) frame where the trace, going from the peak towards `limit`, falls to `level`. NaN if never."""
    frame = peak
    while frame != limit and trace[frame] > level:
        frame += step
    if trace[frame] > level:
        return np.nan
    inside = frame - step  # the last frame above the level
    a, b = trace[inside], trace[frame]
    return inside + step * (a - level) / (a - b) if a != b else float(frame)
