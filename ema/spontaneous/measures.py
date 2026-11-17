"""Measuring spontaneous events, recordings and slices.

Per event, from the dF/F movie the detector searched:

- the trace at the event's maximum, pooled over space like the detection
  (the spatial filter, without the time filter): its peak, rise, decay;
- an isotropic Gaussian fitted to the event's peak map: its width, fitted
  peak and size, and the event's centre;
- its place: distances to the ROI centre and to the electrode.

Per recording and per slice: counts, rates, the controls, and how events
are spread over the slice and over time. The measures are listed in
catalogue.py, with their full descriptions in measure_details.py. Values that
cannot be measured are NaN.
"""

import math
import warnings

import numpy as np
from scipy import ndimage, optimize

from .detection import space_filter

TRACE_BEFORE, TRACE_AFTER = 60, 200  # frames of the event trace before and after the onset
PEAK_SEARCH = (-10, 80)  # frames, from the onset, in which the trace's peak is looked for
BASELINE_END = -10  # the trace's baseline is its median up to this frame from the onset
MAP_BASELINE = (-45, -15)  # frames, from the onset, whose mean the peak map is measured from
MAP_FRAMES = (-5, 40)  # frames, from the onset, in which the map's peak is looked for
MAP_PEAK_SEARCH = 35  # …within the first this many of them
MAP_MEAN = (3, 5)  # the peak map is the mean from this many frames before the map's peak to this many after (excluded)
NEAR_UM, FAR_UM, SHIFT_UM = 48.0, 480.0, 128.0  # the peak map's centre disc; its far field; how far the fit may move
FAR_PIXELS = 100  # the far field's median is taken off the map when it has more pixels than this
FIT_PIXELS = 200  # the width is fitted only with at least this many tissue pixels within the fit radius
SIGMA_UM = (8.0, 400.0)  # the bounds of the fitted σ
DECAY_FIT_FRAMES = 80  # frames from the peak fitted with an exponential for the decay time constant


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def measure_events(detection, settings, center, electrode):
    """Every event measure of every event of a detection, as a list of dicts (one per event)."""
    distance_to_electrode = None
    side = None
    if electrode is not None and electrode.any():
        distance_to_electrode = ndimage.distance_transform_edt(~electrode) * settings.pixel_um
        rows, cols = np.nonzero(electrode)
        if center is not None:
            side = np.array([cols.mean() - center[0], rows.mean() - center[1]])
    found = []
    for frame, row, col, z in detection.events:
        values = {"onset": frame * settings.frame_ms / 1000, "strength": z}
        onset = int(frame) - detection.first_frame
        values.update(_time_course(detection, settings, onset, int(row), int(col)))
        fit = _fit_width(detection, settings, onset, int(row), int(col))
        values.update(fit)
        good = (np.isfinite(fit["fit quality"]) and fit["fit quality"] >= settings.good_fit_r2
                and fit["width"] < settings.max_width_um and fit["fitted peak"] > 0)
        if not good:
            for key in ("fitted peak", "width", "full width at half maximum", "half-maximum area", "size"):
                values[key] = np.nan
        x, y = (values.pop("_fx"), values.pop("_fy")) if good else (float(col), float(row))
        values.pop("_fx", None), values.pop("_fy", None)
        values["x"], values["y"] = x * settings.pixel_um, y * settings.pixel_um
        values["distance to the ROI centre"] = (math.hypot(x - center[0], y - center[1]) * settings.pixel_um
                                                    if center is not None else np.nan)
        values["distance to the electrode"] = (float(distance_to_electrode[int(row), int(col)])
                                               if distance_to_electrode is not None else np.nan)
        values["electrode side"] = float(np.dot([x - center[0], y - center[1]], side) > 0) if side is not None else np.nan
        found.append(values)
    return found


def event_trace(detection, settings, onset, row, col):
    """The pooled dF/F trace at a pixel from TRACE_BEFORE frames before an onset to TRACE_AFTER after, or None."""
    d = detection.dff
    if onset - TRACE_BEFORE < 0 or onset + TRACE_AFTER > d.shape[0]:
        return None
    return space_filter(d[onset - TRACE_BEFORE : onset + TRACE_AFTER], detection.tissue, settings)[:, row, col]


def _time_course(detection, settings, onset, row, col):
    keys = ("local peak", "time to peak", "rise 10-90", "rise speed", "half-width", "half-decay", "decay tau", "area")
    found = dict.fromkeys(keys, np.nan)
    trace = event_trace(detection, settings, onset, row, col)
    if trace is not None:
        found.update(time_course(trace, settings.frame_ms))
    return found


def time_course(trace, frame_ms):
    """The time-course measures of a pooled trace that starts TRACE_BEFORE frames before the onset.

    The trace is taken relative to its median before the onset (up to 10
    frames before it) and smoothed over 3 frames; the peak is looked for
    from 10 frames before the onset to 80 after it.
    """
    found = {}
    start = TRACE_BEFORE + BASELINE_END
    s = ndimage.uniform_filter1d(trace - np.median(trace[:start]), 3)
    peak_at = start + int(np.argmax(s[start : TRACE_BEFORE + PEAK_SEARCH[1]]))
    peak = s[peak_at]
    if peak <= 0:
        return found
    found["local peak"] = peak * 100
    found["time to peak"] = (peak_at - TRACE_BEFORE) * frame_ms
    rising = s[: peak_at + 1]
    below10, below90, below50 = (np.flatnonzero(rising < f * peak) for f in (0.1, 0.9, 0.5))
    if below10.size and below90.size and below90[-1] > below10[-1]:
        found["rise 10-90"] = (below90[-1] - below10[-1]) * frame_ms
        found["rise speed"] = 0.8 * peak * 100 / (found["rise 10-90"] / 1000)
    after50 = np.flatnonzero(s[peak_at:] < 0.5 * peak)
    if after50.size:
        found["half-decay"] = after50[0] * frame_ms
        if below50.size:
            found["half-width"] = (peak_at + after50[0] - below50[-1]) * frame_ms
    after10 = np.flatnonzero(s[peak_at:] < 0.1 * peak)
    if below10.size:
        end = peak_at + (after10[0] if after10.size else len(s) - peak_at)
        found["area"] = s[below10[-1] + 1 : end].sum() * 100 * frame_ms / 1000
    found["decay tau"] = _decay_tau(s[peak_at : peak_at + DECAY_FIT_FRAMES], frame_ms)
    return found


def _decay_tau(segment, frame_ms):
    if len(segment) < 10 or segment[0] <= 0:
        return np.nan
    x = np.arange(len(segment), dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            (a, tau, c), _ = optimize.curve_fit(lambda t, a, tau, c: a * np.exp(-t / tau) + c, x, segment,
                                                p0=(segment[0], 20.0, 0.0), bounds=([0, 0.5, -np.inf], [np.inf, 5000, np.inf]),
                                                maxfev=5000)
        except (RuntimeError, ValueError):
            return np.nan
    return tau * frame_ms if 0.5 * 1.001 < tau < 5000 * 0.999 else np.nan


def gaussian(xy, peak, sigma, offset, x0, y0):
    x, y = xy
    return peak * np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2 * sigma * sigma)) + offset


def peak_map(detection, onset, row, col, settings):
    """The event's peak map (dF/F, lightly blurred, the far field's median taken off), or None near the recording's ends."""
    d = detection.dff
    if onset + MAP_BASELINE[0] < 0 or onset + MAP_FRAMES[1] > d.shape[0]:
        return None
    window = d[onset + MAP_FRAMES[0] : onset + MAP_FRAMES[1]] - d[onset + MAP_BASELINE[0] : onset + MAP_BASELINE[1]].mean(0)
    window = ndimage.gaussian_filter(window, (0, 1, 1))
    rows, cols = np.indices(detection.tissue.shape)
    distance = np.hypot(cols - col, rows - row)
    near = distance <= NEAR_UM / settings.pixel_um
    at = int(np.argmax(ndimage.uniform_filter1d(window[:, near].mean(1), 5)[:MAP_PEAK_SEARCH]))
    image = window[max(at - MAP_MEAN[0], 0) : at + MAP_MEAN[1]].mean(0)
    far = detection.tissue & (distance > FAR_UM / settings.pixel_um)
    if far.sum() > FAR_PIXELS:
        image = image - np.median(image[far])
    return image


def _fit_width(detection, settings, onset, row, col):
    found = {"fitted peak": np.nan, "width": np.nan, "full width at half maximum": np.nan, "half-maximum area": np.nan,
             "size": np.nan, "fit quality": np.nan, "_fx": np.nan, "_fy": np.nan}
    image = peak_map(detection, onset, row, col, settings)
    if image is None:
        return found
    rows, cols = np.indices(image.shape)
    inside = detection.tissue & (np.hypot(cols - col, rows - row) <= settings.pixels(settings.fit_radius_um))
    if inside.sum() < FIT_PIXELS:
        return found
    xs, ys, values = cols[inside].astype(float), rows[inside].astype(float), image[inside]
    shift, low, high = (settings.pixels(v) for v in (SHIFT_UM, *SIGMA_UM))
    try:
        p, _ = optimize.curve_fit(gaussian, (xs, ys), values, p0=(float(np.percentile(values, 99)), 4.0, 0.0, col, row),
                                  bounds=([0, low, -0.05, col - shift, row - shift], [1.0, high, 0.05, col + shift, row + shift]),
                                  maxfev=4000)
    except (RuntimeError, ValueError):
        return found
    r2 = 1 - np.sum((values - gaussian((xs, ys), *p)) ** 2) / np.sum((values - values.mean()) ** 2)
    sigma_um = p[1] * settings.pixel_um
    found.update({
        "fitted peak": p[0] * 100,
        "width": sigma_um,
        "full width at half maximum": 2 * math.sqrt(2 * math.log(2)) * sigma_um,
        "half-maximum area": math.pi * (math.sqrt(2 * math.log(2)) * sigma_um / 1000) ** 2,
        "size": p[0] * 100 * 2 * math.pi * (sigma_um / 1000) ** 2,
        "fit quality": float(r2),
        "_fx": float(p[3]),
        "_fy": float(p[4]),
    })
    return found


# ---------------------------------------------------------------------------
# Recordings and slices
# ---------------------------------------------------------------------------


def measure_recording(detection, settings):
    """The per-recording measures of a detection."""
    minutes = detection.searched_frames * settings.frame_ms / 60000
    area = detection.tissue.sum() * (settings.pixel_um / 1000) ** 2
    count = len(detection.events)
    return {
        "events": count,
        "searched time": minutes * 60,
        "rate": count / minutes if minutes > 0 else np.nan,
        "tissue area": area,
        "density": count / minutes / area if minutes > 0 and area > 0 else np.nan,
        "sign-flipped": np.nan if detection.sign_flipped is None else len(detection.sign_flipped),
        "time-reversed": np.nan if detection.time_reversed is None else len(detection.time_reversed),
        "pixel noise": detection.pixel_noise,
    }


def summarise_slice(recordings, events, settings, tissue, seed=0):
    """The per-slice measures of SLICE, from the per-recording values and the events of all recordings of a slice.

    `recordings` is a list of per-recording dicts; `events` a list of
    (recording index, event dict); `tissue` the searched pixels (for the
    clustering index). The summaries of event measures, such as
    'width median', are made by `summarise_events`.
    """
    minutes = sum(r["searched time"] for r in recordings) / 60
    count = sum(r["events"] for r in recordings)
    flipped = sum(r["sign-flipped"] for r in recordings) if recordings else np.nan
    reversed_ = sum(r["time-reversed"] for r in recordings) if recordings else np.nan
    area = np.mean([r["tissue area"] for r in recordings]) if recordings else np.nan
    rate = count / minutes if minutes > 0 else np.nan
    found = {
        "events": count,
        "searched time": minutes,
        "rate": rate,
        "density": rate / area if area > 0 else np.nan,
        "sign-flipped rate": flipped / minutes if minutes > 0 else np.nan,
        "time-reversed rate": reversed_ / minutes if minutes > 0 else np.nan,
        "rate above the sign-flip floor": (count - flipped) / minutes if minutes > 0 else np.nan,
        "sign-flipped share": flipped / count if count else np.nan,
    }
    values = [e for _, e in events]
    distances = np.array([e["distance to the ROI centre"] for e in values], float)
    distances = distances[np.isfinite(distances)]
    found["share near the ROI centre"] = float(np.mean(distances < settings.near_um)) if len(distances) else np.nan
    sides = np.array([e["electrode side"] for e in values], float)
    found["share on the electrode side"] = float(np.nanmean(sides)) if np.isfinite(sides).any() else np.nan
    points = np.array([(e["x"], e["y"]) for e in values], float).reshape(-1, 2)
    found["nearest-neighbour distance"] = _nearest_median(points)
    found["clustering index"] = clustering_index(points, tissue, settings, seed)
    sites = _sites(points, settings.site_um)
    sizes = np.bincount(sites) if len(sites) else np.zeros(0, int)
    found["recurring sites"] = int((sizes >= 2).sum()) if values else np.nan
    found["share at recurring sites"] = float(np.mean(sizes[sites] >= 2)) if values else np.nan
    found["share together"] = _share_together(events, settings.together_ms) if values else np.nan
    event_size = np.array([e["size"] for e in values], float)
    found["release per minute"] = rate * np.nanmedian(event_size) if np.isfinite(event_size).any() else np.nan
    return found


def summarise_events(events, keys, statistics):
    """{'<key> <statistic>': value} of event measures over a slice's events (empty values left out)."""
    found = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for key in keys:
            column = np.array([e.get(key, np.nan) for e in events], float)
            for statistic in statistics:
                function = {"median": np.nanmedian, "mean": np.nanmean, "min": np.nanmin, "max": np.nanmax}[statistic]
                found[f"{key} {statistic}"] = float(function(column)) if np.isfinite(column).any() else np.nan
    return found


def _nearest_median(points):
    if len(points) < 2:
        return np.nan
    distance = np.hypot(*(points[:, None, :] - points[None, :, :]).transpose(2, 0, 1))
    np.fill_diagonal(distance, np.inf)
    return float(np.median(distance.min(1)))


def clustering_index(points, tissue, settings, seed=0, draws=200):
    """The median nearest-neighbour distance of the events ÷ its mean over `draws` sets of as many random tissue points.

    Below 1: events are closer together than chance (they cluster); about 1:
    no clustering. The random points are drawn with a fixed seed, so the
    same slice always gives the same number. NaN with fewer than 2 events.
    """
    observed = _nearest_median(points)
    if not np.isfinite(observed) or tissue is None or not tissue.any():
        return np.nan
    rows, cols = np.nonzero(tissue)
    rng = np.random.default_rng(seed)
    expected = []
    for _ in range(draws):
        pick = rng.integers(0, len(rows), len(points))
        random = np.column_stack([cols[pick], rows[pick]]) * settings.pixel_um
        expected.append(_nearest_median(random))
    return observed / float(np.mean(expected))


def _sites(points, radius_um):
    """A site number for each point; points closer than radius_um (directly or through others) share one."""
    if not len(points):
        return np.zeros(0, int)
    distance = np.hypot(*(points[:, None, :] - points[None, :, :]).transpose(2, 0, 1))
    _, labels = _components(distance < radius_um)
    return labels


def _components(adjacent):
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    return connected_components(csr_matrix(adjacent), directed=False)


def _share_together(events, together_ms):
    by_recording = {}
    for recording, e in events:
        by_recording.setdefault(recording, []).append(e["onset"] * 1000)
    together = 0
    for onsets in by_recording.values():
        onsets = np.array(onsets)
        gaps = np.abs(onsets[:, None] - onsets[None, :])
        np.fill_diagonal(gaps, np.inf)
        together += int((gaps.min(1) <= together_ms).sum()) if len(onsets) > 1 else 0
    return together / len(events)
