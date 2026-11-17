"""Spatial measures: how the response of a pulse is spread over the slice around the ROI centre.

A pulse's response map is the response of every pixel (as for the trace: a
change from the pulse's baseline in percent) averaged over a few frames
around the peak of the ROI trace. Distances are measured from the ROI centre
in rings one pixel wide. Pixels under the electrode can be left out.

The measures are made in four steps, each giving the measures of one set of
keys (below). A new spatial measure is computed in one of the steps and its
key added to that step's set; a test checks that every measure of the
catalogue belongs to one step.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage, stats
from scipy.optimize import curve_fit

from .protocol import BRIGHTNESS

FOOTPRINT_KEYS = ("footprint width", "footprint half-width", "r50", "tail fraction")  # see footprint()
UNEVENNESS_KEYS = ("centroid offset", "elongation", "heterogeneity", "hot spots")  # see centroid_and_unevenness()
RELEASE_KEYS = ("latency slope", "far-near delay")  # see release_spread()
DECAY_KEYS = ("far-near decay ratio", "decay-distance slope")  # see decay_measures()


@dataclass
class SpatialResult:
    """The spatial measures of one recording, and what they were made from (for drawing them)."""

    values: dict = field(default_factory=dict)  # measure name -> number
    maps: dict = field(default_factory=dict)  # pulse name -> response map (%)
    profiles: dict = field(default_factory=dict)  # pulse name -> ring averages (one per ring)
    fits: dict = field(default_factory=dict)  # pulse name -> (a, λ in µm, c) of the footprint fit, or None
    centroids: dict = field(default_factory=dict)  # pulse name -> (x, y) of the signal-weighted centre
    latencies: dict = field(default_factory=dict)  # pulse name -> half-rise latency of every pixel (ms)
    decays: dict = field(default_factory=dict)  # pulse name -> Decay: the bands and rings from the peak on
    radii_um: np.ndarray = None  # mean distance of each ring from the ROI centre


@dataclass
class Decay:
    """How a pulse's response map decays from its peak on, one time point per bin of frames."""

    times_ms: np.ndarray  # middle of each bin, after the peak frame of the ROI trace
    near: np.ndarray  # mean of the ring averages in the near band (%)
    far: np.ndarray  # the same in the far band (%)
    half_decay_ms: np.ndarray  # half-decay time of each ring (ms), for the rings out to the end of the far band


def lorentzian(r, a, width, c):
    return a / (1 + (r / width) ** 2) + c


def fit_lorentzian(r, profile, start_width=300.0):
    """(a, λ, c) of the Lorentzian fitted to a ring profile, or None. λ is bounded to 10–5000 µm."""
    ok = np.isfinite(profile)
    if ok.sum() < 8 or not np.isfinite(profile[0]) or profile[0] <= 0:
        return None
    try:
        parameters, _ = curve_fit(lorentzian, r[ok], profile[ok], p0=[profile[0], start_width, 0],
                                  bounds=([0, 10, -100], [1000, 5000, 100]), maxfev=20000)
    except (RuntimeError, ValueError):
        return None
    return tuple(parameters)


def valid_width(width):
    return 11 < width < 4999


# ---------------------------------------------------------------------------
# Maps and rings
# ---------------------------------------------------------------------------


def response_movie(protocol, movie, baseline_window, frames):
    """The response (%) of every pixel in `frames` (a slice), relative to the mean over the baseline window."""
    base = movie[baseline_window.start : baseline_window.end].mean(axis=0)
    part = movie[frames]
    if protocol.trace == BRIGHTNESS:
        return (part / np.maximum(base, 1e-9) - 1) * 100
    return part - base


def response_map(protocol, movie, baseline_window, peak_frame):
    settings = protocol.spatial
    first = max(peak_frame - settings.frames_before_peak, 0)
    frames = slice(first, peak_frame + settings.frames_from_peak)
    image = response_movie(protocol, movie, baseline_window, frames).mean(axis=0)
    return ndimage.gaussian_filter(image, settings.smoothing_px) if settings.smoothing_px > 0 else image


def noise_map(protocol, movie, baseline_window):
    """A map made like a response map from frames of the baseline window itself: what noise alone gives."""
    settings = protocol.spatial
    count = settings.frames_before_peak + settings.frames_from_peak
    frames = slice(baseline_window.start, min(baseline_window.start + count, baseline_window.end))
    image = response_movie(protocol, movie, baseline_window, frames).mean(axis=0)
    return ndimage.gaussian_filter(image, settings.smoothing_px) if settings.smoothing_px > 0 else image


def ring_index(shape, center):
    y, x = np.indices(shape)
    return np.hypot(x - center[0], y - center[1]).astype(int)


def ring_radii(shape, center, count):
    """The mean distance (in pixels) of the pixels of each ring from the centre: about k + 0.5 for ring k."""
    y, x = np.indices(shape)
    distance = np.hypot(x - center[0], y - center[1])
    rings = distance.astype(int)
    keep = rings < count
    pixels = np.bincount(rings[keep], minlength=count)
    radii = np.bincount(rings[keep], distance[keep], minlength=count) / np.maximum(pixels, 1)
    return np.where(pixels > 0, radii, np.arange(count) + 0.5)


def ring_profile(image, rings, count, exclude=None):
    """The mean of each ring (one pixel wide) out to `count` rings. A ring less than 25 % inside the image is NaN."""
    keep = rings < count
    if exclude is not None:
        keep &= ~exclude
    total = np.bincount(rings[keep], image[keep], minlength=count)
    pixels = np.bincount(rings[keep], minlength=count)
    profile = total / np.maximum(pixels, 1)
    cover = pixels / np.maximum(1, 2 * np.pi * (np.arange(count) + 0.5))
    profile[cover < 0.25] = np.nan
    return profile


def fill_excluded(image, rings, exclude):
    """The image with excluded pixels replaced by the mean of the visible pixels of their ring."""
    if exclude is None or not exclude.any():
        return image
    count = rings.max() + 1
    visible = ~exclude
    total = np.bincount(rings[visible], image[visible], minlength=count)
    pixels = np.bincount(rings[visible], minlength=count)
    ring_mean = np.where(pixels > 0, total / np.maximum(pixels, 1), 0.0)
    filled = image.copy()
    filled[exclude] = ring_mean[rings[exclude]]
    return filled


def band_mean(profile, low_um, high_um, pixel_um):
    rings = np.arange(len(profile)) * pixel_um
    inside = (rings >= low_um) & (rings < high_um) & np.isfinite(profile)
    return profile[inside].mean() if inside.any() else np.nan


# ---------------------------------------------------------------------------
# The measures
# ---------------------------------------------------------------------------


def footprint(profile, radii, settings):
    """Width λ (Lorentzian fit), half-width, r50 and tail fraction of a ring profile, and the fit's parameters.

    `radii` are the mean distances of the rings from the centre, in pixels.
    """
    px = settings.pixel_um
    found = dict.fromkeys(FOOTPRINT_KEYS, np.nan)
    r = radii * px
    fit = fit_lorentzian(r, profile)
    if fit is not None and valid_width(fit[1]):
        found["footprint width"] = fit[1]

    inner = int(round(settings.integrate_um / px))
    if np.isfinite(profile[:inner]).all() and len(profile) >= inner and profile[0] > 0:
        signal = np.clip(profile[:inner], 0, None)
        radius = (np.arange(inner) + 0.5) * px
        weight = signal * 2 * np.pi * radius
        total = weight.sum()
        if total > 0:
            found["r50"] = np.interp(0.5, np.cumsum(weight) / total, radius)
            found["tail fraction"] = weight[int(round(settings.tail_from_um / px)):].sum() / total
        half = 0.5 * np.nanmax(profile[:3])
        below = np.flatnonzero(profile[:inner] < half)
        if below.size and below[0] > 0:
            k = below[0]
            found["footprint half-width"] = np.interp(half, [profile[k], profile[k - 1]], [r[k], r[k - 1]])
    return found, fit


def centroid_and_unevenness(image, noise, profile, rings, center, exclude, settings):
    """Centroid offset (µm), elongation, heterogeneity and hot spots per mm², with the centroid itself."""
    px = settings.pixel_um
    count = len(profile)
    model = profile[np.minimum(rings, count - 1)]
    region = (rings * px < settings.region_um) & np.isfinite(model)
    visible = region if exclude is None else region & ~exclude
    model = np.nan_to_num(model)

    weights = np.clip(fill_excluded(image, rings, exclude), 0, None) * region
    found = dict.fromkeys(UNEVENNESS_KEYS, np.nan)
    centroid = None
    if weights.sum() > 0:
        y, x = np.indices(image.shape)
        total = weights.sum()
        centroid = ((weights * x).sum() / total, (weights * y).sum() / total)
        found["centroid offset"] = np.hypot(centroid[0] - center[0], centroid[1] - center[1]) * px
        dx, dy = x - centroid[0], y - centroid[1]
        moments = np.array([[(weights * dx * dx).sum(), (weights * dx * dy).sum()],
                            [(weights * dx * dy).sum(), (weights * dy * dy).sum()]]) / total
        smallest, largest = np.linalg.eigvalsh(moments)
        if smallest > 0:
            found["elongation"] = np.sqrt(largest / smallest)

    noise_profile = ring_profile(noise, rings, count, exclude)
    noise_residual = (noise - np.nan_to_num(noise_profile[np.minimum(rings, count - 1)]))[visible]
    residual = (image - model)[visible]
    signal = np.nanmean(image[visible]) if visible.any() else np.nan
    if visible.any() and signal > 0:
        found["heterogeneity"] = np.sqrt(max(np.var(residual) - np.var(noise_residual), 0.0)) / signal
        residual_map = np.where(visible, image - model, -np.inf)
        noise_sd = np.std(noise_residual)
        peaks = (residual_map == ndimage.maximum_filter(residual_map, size=5)) & (residual_map > 3 * noise_sd)
        found["hot spots"] = peaks.sum() / (visible.sum() * (px / 1000) ** 2)
    return found, centroid


def near_to_far(map_a, map_b, rings, count, exclude, settings):
    """(map_a ÷ map_b in the far band) ÷ (map_a ÷ map_b in the near band), from ring averages."""
    s = settings
    profile_a, profile_b = ring_profile(map_a, rings, count, exclude), ring_profile(map_b, rings, count, exclude)

    def ratio(low, high):
        below = band_mean(profile_b, low, high, s.pixel_um)
        return band_mean(profile_a, low, high, s.pixel_um) / below if below > 1.0 else np.nan  # less than 1 % is noise

    near, far = ratio(s.near_from_um, s.near_to_um), ratio(s.far_from_um, s.far_to_um)
    return far / near if near and np.isfinite(near) and near > 0 else np.nan


def release_spread(protocol, movie, baseline_window, stimulus, window, rings, exclude):
    """Latency slope (ms/mm), far-near delay (ms), and the half-rise latency of every pixel (ms after the stimulus).

    Each pixel's response is smoothed over 3 frames and 1.5 pixels. Pixels whose
    peak is more than 10 baseline SDs and 30 % of the strongest pixels' peak get
    a latency: the time the response, going back from its peak, falls to half.
    """
    s = protocol.spatial
    dt = protocol.sampling_interval_ms
    shape = movie.shape[1:]
    nothing = (dict.fromkeys(RELEASE_KEYS, np.nan), np.full(shape, np.nan))
    if stimulus is None or window is None:
        return nothing
    first = min(stimulus, window.start)
    last = min(window.end, len(movie))
    def smooth(part):
        return ndimage.gaussian_filter(ndimage.uniform_filter1d(part, 3, axis=0), (0, 1.5, 1.5))

    response = smooth(response_movie(protocol, movie, baseline_window, slice(first, last)))
    noise = smooth(response_movie(protocol, movie, baseline_window, slice(baseline_window.start, baseline_window.end))).std(axis=0)
    peak = response.max(axis=0)
    at_peak = response.argmax(axis=0)
    good = (peak > 10 * noise) & (peak > 0.3 * np.percentile(peak, 99.9))
    if exclude is not None:
        good &= ~exclude

    frame = np.arange(len(response))[:, None, None]
    below = (response <= 0.5 * peak) & (frame <= at_peak)
    found = below.any(axis=0)
    crossing = len(response) - 1 - np.argmax(below[::-1], axis=0)  # the last frame at or below half before the peak
    good &= found & (crossing < at_peak)
    latency = np.full(shape, np.nan)
    y, x = np.nonzero(good)
    if y.size:
        a, b = response[crossing[y, x], y, x], response[crossing[y, x] + 1, y, x]
        level = 0.5 * peak[y, x]
        where = crossing[y, x] + np.where(b != a, (level - a) / (b - a), 0)
        latency[y, x] = (first + where - stimulus) * dt

    count = int(s.far_to_um / s.pixel_um) + 1
    medians = np.full(count, np.nan)
    for k in range(count):
        ring = good & (rings == k)
        if ring.sum() >= max(3, 0.3 * 2 * np.pi * (k + 0.5)):
            medians[k] = np.median(latency[ring])
    distance_mm = np.arange(count) * s.pixel_um / 1000
    ok = np.isfinite(medians)
    values = {"latency slope": stats.theilslopes(medians[ok], distance_mm[ok])[0] if ok.sum() >= 10 else np.nan}
    values["far-near delay"] = band_mean(medians, s.far_from_um, s.far_to_um, s.pixel_um) - band_mean(medians, s.near_from_um, s.near_to_um, s.pixel_um)
    return values, latency


# ---------------------------------------------------------------------------
# Decay with distance
# ---------------------------------------------------------------------------

def decay_end(protocol, movie, peak_frame, recording=None):
    """The frame the decay is followed up to (not included): the next stimulus, the end of the recording,
    or the longest time to follow, whichever comes first."""
    end = min(len(movie), peak_frame + int(round(protocol.spatial.follow_ms / protocol.sampling_interval_ms)))
    for pulse in protocol.pulses:
        stimulus, _ = protocol.pulse_timing(pulse, recording)
        if stimulus is not None and stimulus > peak_frame:
            end = min(end, stimulus)
    return end


def half_time(times, curve):
    """Time at which a curve, starting at its first value, first falls to half of it (straight-line between points)."""
    if not len(curve) or not np.isfinite(curve[0]) or curve[0] <= 0:
        return np.nan
    level = curve[0] / 2
    below = np.flatnonzero(curve <= level)
    if not below.size:
        return np.nan
    k = below[0]
    if not np.isfinite(curve[k - 1]):
        return np.nan
    return np.interp(level, [curve[k], curve[k - 1]], [times[k], times[k - 1]])


def decay_course(protocol, movie, baseline_window, peak_frame, end_frame, rings, count, exclude):
    """The ring averages and bands from the peak on, in bins as long as the response map, which is the first bin."""
    s = protocol.spatial
    dt = protocol.sampling_interval_ms
    size = s.frames_before_peak + s.frames_from_peak
    first = max(peak_frame - s.frames_before_peak, 0)
    bins = max((end_frame - first) // size, 0)
    starts = first + size * np.arange(bins)
    response = response_movie(protocol, movie, baseline_window, slice(first, first + size * bins))
    maps = response.reshape(bins, size, *response.shape[1:]).mean(axis=1)  # one map per bin
    if s.smoothing_px > 0:
        maps = ndimage.gaussian_filter(maps, (0, s.smoothing_px, s.smoothing_px))  # blurring the mean = the mean of blurs
    profiles = np.array([ring_profile(image, rings, count, exclude) for image in maps]).reshape(bins, count)
    times = (starts + (size - 1) / 2 - peak_frame) * dt
    near = np.array([band_mean(p, s.near_from_um, s.near_to_um, s.pixel_um) for p in profiles])
    far = np.array([band_mean(p, s.far_from_um, s.far_to_um, s.pixel_um) for p in profiles])
    last_ring = min(int(s.far_to_um / s.pixel_um) + 1, count)
    half_decay = np.array([half_time(times, profiles[:, k]) for k in range(last_ring)]) if bins else np.array([])
    return Decay(times, near, far, half_decay)


def decay_measures(decay, settings):
    """Far-near decay ratio and decay-distance slope (ms/mm)."""
    found = dict.fromkeys(DECAY_KEYS, np.nan)
    near, far = half_time(decay.times_ms, decay.near), half_time(decay.times_ms, decay.far)
    if near > 0:
        found["far-near decay ratio"] = far / near
    rings = decay.half_decay_ms
    distance_mm = np.arange(len(rings)) * settings.pixel_um / 1000
    ok = np.isfinite(rings)
    if ok.sum() >= 10:
        found["decay-distance slope"] = stats.theilslopes(rings[ok], distance_mm[ok])[0]
    return found


def measure_spatial(protocol, movie, center, electrode, measurement, recording=None, pulses=None, with_decay=False):
    """The spatial measures of a recording.

    `movie` is the signal of every pixel the protocol measures (see
    ema.evoked.traces), frames first. `measurement` is the measurement of the
    ROI trace, whose peak frames place the maps. `pulses` are the pulses to
    make maps of; by default the protocol's spatial pulses. With
    `with_decay`, the decay with distance is followed even when none of its
    measures is chosen (for drawing it).
    """
    s = protocol.spatial
    result = SpatialResult()
    exclude = electrode if s.exclude_electrode and electrode is not None else None
    rings = ring_index(movie.shape[1:], center)
    count = int(s.max_radius_um / s.pixel_um) + 1
    result.radii_um = ring_radii(movie.shape[1:], center, count) * s.pixel_um
    wanted = protocol.spatial_pulses if pulses is None else pulses
    near_to_far_pulses = {p for name in protocol.near_to_far for c in protocol.comparisons if c.name == name for p in (c.pulse, c.relative_to)}

    for name in dict.fromkeys(list(wanted) + sorted(near_to_far_pulses)):
        pulse = protocol.pulse(name)
        baseline = protocol.baseline_window(pulse.baseline, recording) if pulse else None
        stimulus, window = protocol.pulse_timing(pulse, recording) if pulse else (None, None)
        if baseline is None or name not in measurement.peaks:
            continue
        peak_frame = measurement.peaks[name][0]
        image = response_map(protocol, movie, baseline, peak_frame)
        profile = ring_profile(image, rings, count, exclude)
        result.maps[name], result.profiles[name] = image, profile
        if name not in wanted:
            continue
        chosen = set(protocol.spatial_measures)
        sizes, result.fits[name] = footprint(profile, result.radii_um / s.pixel_um, s)
        spread, centroid = centroid_and_unevenness(image, noise_map(protocol, movie, baseline), profile, rings, center, exclude, s)
        result.centroids[name] = centroid
        values = {**sizes, **spread}
        if chosen & set(RELEASE_KEYS):
            timing, result.latencies[name] = release_spread(protocol, movie, baseline, stimulus, window, rings, exclude)
            values.update(timing)
        if chosen & set(DECAY_KEYS) or with_decay:
            end = decay_end(protocol, movie, peak_frame, recording)
            result.decays[name] = decay_course(protocol, movie, baseline, peak_frame, end, rings, count, exclude)
            values.update(decay_measures(result.decays[name], s))
        for key in protocol.spatial_measures:
            result.values[f"{name} {key}"] = values[key]

    for name in wanted:  # a pulse that could not be measured still gets its (empty) values
        for key in protocol.spatial_measures:
            result.values.setdefault(f"{name} {key}", np.nan)
    for comparison in protocol.comparisons:
        if comparison.name in protocol.near_to_far:
            a, b = result.maps.get(comparison.pulse), result.maps.get(comparison.relative_to)
            value = near_to_far(a, b, rings, count, exclude, s) if a is not None and b is not None else np.nan
            result.values[f"{comparison.name} near-to-far"] = value
    return result
