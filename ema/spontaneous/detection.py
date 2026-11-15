"""The spontaneous-event detector (detector v5 of the metric study), step by step.

1. dF/F of every pixel against a polynomial fitted over time (bleaching),
   then a running median over a few frames (camera spikes).
2. A matched filter in time: the event template, fitted with a straight-line
   baseline at every frame.
3. A matched filter in space: a Gaussian over the tissue only.
4. Each filtered frame's median over the tissue is subtracted (the
   field-wide signal).
5. z = (output − its median) ÷ (1.4826 × its median absolute deviation),
   pixel by pixel.
6. An event is a connected region of z ≥ the region threshold whose maximum
   reaches the event threshold θ, placed at that maximum.
7. Of two regions of opposite sign close in time and place, only the
   stronger counts (the template's echoes).
8. Onsets in the last part of the searched range are not counted.

The same search on the movie turned upside down (sign-flipped) and played
backwards (time-reversed) gives the controls. Nothing here needs the GUI.
Frames are counted as in the rest of EMA (frame 0 is the second frame of
the file); positions are (row, column) in pixels.
"""

from dataclasses import dataclass, field

import numpy as np
import scipy.fft as sfft
from scipy import ndimage

ECHO_MIN_Z = 5.0  # regions weaker than this neither count nor veto (unless the event threshold is lower)
NEIGHBOURS = np.ones((3, 3, 3), bool)  # regions are connected through faces, edges and corners in time and space


@dataclass
class Detection:
    """The result of searching one recording."""

    events: np.ndarray  # (n, 4): onset frame (in the recording), row, column, z
    sign_flipped: np.ndarray = None  # the same, for the sign-flipped movie (None if not searched)
    time_reversed: np.ndarray = None  # the same, for the time-reversed movie (onsets in reversed time)
    searched_frames: int = 0  # the frames whose onsets are counted
    first_onset: int = 0  # the first frame an onset can have
    tissue: np.ndarray = None  # True for the pixels searched
    peak_z: np.ndarray = None  # each pixel's largest z over the recording, for display
    dff: np.ndarray = field(default=None, repr=False)  # the dF/F movie searched (frames left out removed)
    first_frame: int = 0  # the recording's frame that is frame 0 of `dff`
    pixel_noise: float = float("nan")  # % dF/F, before the spike filter (see pixel_noise)

    def count(self, which, threshold):
        found = getattr(self, which)
        return None if found is None else int((found[:, 3] >= threshold).sum())


# ---------------------------------------------------------------------------
# The steps
# ---------------------------------------------------------------------------


def resting_brightness(stack, settings):
    """Each pixel's mean over the resting brightness window (F0)."""
    start, stop = settings.brightness_frames
    return stack[start:stop].astype(np.float32).mean(0)


def tissue_mask(f0, electrode, settings):
    """The pixels searched: blocks that are bright enough and mostly off the electrode.

    A block is left out when its resting brightness is below `dark_fraction`
    of the median block's, or when at least `electrode_fraction` of it is
    under the electrode. Pixels of an incomplete block at the image edge are
    left out.
    """
    b = settings.block_px
    rows, cols = (f0.shape[0] // b) * b, (f0.shape[1] // b) * b
    blocks = f0[:rows, :cols].reshape(rows // b, b, cols // b, b).mean((1, 3))
    under = np.zeros(f0.shape, bool) if electrode is None else electrode
    covered = under[:rows, :cols].reshape(rows // b, b, cols // b, b).mean((1, 3))
    good = (covered < settings.electrode_fraction) & (blocks > settings.dark_fraction * np.median(blocks))
    mask = np.zeros(f0.shape, bool)
    mask[:rows, :cols] = np.kron(good, np.ones((b, b), bool))
    return mask


def bleach_corrected(frames, settings):
    """dF/F of every pixel against a polynomial fitted over time (float32)."""
    count = frames.shape[0]
    basis = np.vander(np.linspace(-1, 1, count), settings.bleach_order + 1)
    values = frames.reshape(count, -1)
    coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
    return (values / (basis @ coefficients) - 1).astype(np.float32).reshape(frames.shape)


def despiked(d, tissue, settings):
    """A running median over `despike_frames` frames (the end frames kept), 0 outside the tissue."""
    if settings.despike_frames == 3:  # the median of three, written out: much faster than a median filter
        a, b, c = d[:-2], d[1:-1], d[2:]
        d[1:-1] = np.maximum(np.minimum(a, b), np.minimum(np.maximum(a, b), c))
    elif settings.despike_frames > 1:
        d = ndimage.median_filter(d, size=(settings.despike_frames, 1, 1), mode="nearest")
    d[:, ~tissue] = 0
    return d


def dff(frames, tissue, settings):
    """dF/F of every pixel against a polynomial over time, spike-filtered, 0 outside the tissue (float32)."""
    return despiked(bleach_corrected(frames, settings), tissue, settings)


def pixel_noise(d, tissue):
    """The median over the tissue of each pixel's robust SD over time (1.4826 × median absolute deviation), in %."""
    if not tissue.any():
        return np.nan
    pixels = d[:, tissue]
    return float(np.median(np.median(np.abs(pixels - np.median(pixels, 0)), 0)) * 1.4826 * 100)


def kernel(t_ms, decay_ms, rise_ms):
    """The event shape exp(−t/decay) − exp(−t/rise) for t > 0 (0 before), scaled to a peak of 1."""
    t = np.clip(t_ms, 0, None)
    fine = np.linspace(0, 1000, 100001)
    peak = (np.exp(-fine / decay_ms) - np.exp(-fine / rise_ms)).max()
    return np.where(t_ms > 0, (np.exp(-t / decay_ms) - np.exp(-t / rise_ms)) / peak, 0.0)


def template(settings):
    """The time filter and how many frames of it come before the onset.

    It runs from `before_ms` before the onset to `after_ms` after it (whole
    frames: round(before ÷ frame interval) before, the frames that fit in
    `after_ms` after). With `line_baseline`, its projection on a straight
    line is removed, which fits a sloping baseline with it. Scaled to unit
    length (sum of squares 1).
    """
    before = settings.frames(settings.before_ms)
    after = int(settings.after_ms / settings.frame_ms)
    shape = kernel(np.arange(-before, after) * settings.frame_ms, settings.decay_ms, settings.rise_ms)
    if settings.line_baseline:
        line = np.column_stack([np.ones_like(shape), np.arange(len(shape), dtype=float)])
        shape = shape - line @ np.linalg.lstsq(line, shape, rcond=None)[0]
    return shape / np.sqrt((shape**2).sum()), before


def time_filter(d, shape):
    """The template slid along every pixel's trace: output frame i covers frames i to i + len(shape) − 1."""
    count, length = d.shape[0], len(shape)
    n = sfft.next_fast_len(count + length)
    spectrum = sfft.rfft(d.reshape(count, -1), n, axis=0, workers=1)
    spectrum *= np.conj(sfft.rfft(shape.astype(np.float32), n))[:, None]
    return sfft.irfft(spectrum, n, axis=0, workers=1)[: count - length + 1].reshape((count - length + 1,) + d.shape[1:])


def space_filter(movie, tissue, settings):
    """A Gaussian over the tissue only (normalised convolution), minus each frame's median over the tissue."""
    sigma = settings.pixels(settings.blur_um)
    if sigma > 0:
        weight = ndimage.gaussian_filter(tissue.astype(np.float32), sigma, mode="constant", truncate=3.0)
        out = ndimage.gaussian_filter(movie, (0, sigma, sigma), mode="constant", truncate=3.0) / np.maximum(weight, 1e-3)
    else:
        out = movie.copy()
    if settings.remove_field:
        out -= np.median(out[:, tissue], axis=1)[:, None, None]
    return out


def zscore(movie, tissue):
    """(value − median) ÷ (1.4826 × median absolute deviation) per pixel, from every second frame; 0 off the tissue."""
    movie -= np.median(movie[::2], axis=0)
    movie /= np.maximum(np.median(np.abs(movie[::2]), axis=0) * 1.4826, 1e-12)
    movie[:, ~tissue] = 0
    return movie


def regions(z, low, offset):
    """Connected regions of z ≥ low: (onset frame, row, column) of each region's maximum, and that maximum.

    The onset is the frame `offset` frames after the start of the template window.
    """
    labels, count = ndimage.label(z >= low, structure=NEIGHBOURS)
    if count == 0:
        return np.zeros((0, 3)), np.zeros(0)
    inside = np.flatnonzero(labels)
    label_of, value = labels.ravel()[inside], z.ravel()[inside]
    order = np.lexsort((value, label_of))
    last = np.r_[np.flatnonzero(np.diff(label_of[order])), len(order) - 1]
    where = np.column_stack(np.unravel_index(inside[order[last]], z.shape)) + np.array([offset, 0, 0])
    return where, value[order[last]]


def drop_echoes(where, value, other_where, other_value, settings):
    """Regions of one sign without those that are echoes of a stronger region of the other sign."""
    weakest = min(ECHO_MIN_Z, settings.event_z)
    keep = value >= weakest
    where, value = where[keep], value[keep]
    if not settings.echo_rule:
        return where, value
    strong = other_value >= weakest / settings.echo_ratio
    if strong.any() and len(value):
        q, w = other_where[strong], other_value[strong]
        close = (np.abs(where[:, None, 0] - q[None, :, 0]) <= settings.frames(settings.echo_ms)) & (
            np.hypot(where[:, None, 1] - q[None, :, 1], where[:, None, 2] - q[None, :, 2]) <= settings.pixels(settings.echo_um))
        echo = (close & (value[:, None] <= settings.echo_ratio * w[None])).any(1)
        where, value = where[~echo], value[~echo]
    return where, value


# ---------------------------------------------------------------------------
# The whole search
# ---------------------------------------------------------------------------


def z_movie(d, tissue, settings):
    """z of every pixel and onset frame of a dF/F movie, and the template's frames before the onset."""
    shape, before = template(settings)
    return zscore(space_filter(time_filter(d, shape), tissue, settings), tissue), before


def signed_regions(z, before, settings):
    """The regions of z and of −z, each without the echoes of the other."""
    up = regions(z, settings.region_z, before)
    down = regions(-z, settings.region_z, before)
    return drop_echoes(*up, *down, settings), drop_echoes(*down, *up, settings)


def counted(where, value, settings, last_onset):
    """Events: regions reaching the event threshold whose onset is not past the last counted onset."""
    keep = (value >= settings.event_z) & (where[:, 0] <= last_onset)
    return np.column_stack([where[keep], value[keep]]) if keep.any() else np.zeros((0, 4))


def detect(stack, electrode, settings, keep_dff=True):
    """Search one recording (frames, rows, columns) for spontaneous events.

    `electrode` is the electrode mask of the recording's folder (from the ROI
    file), or None. Returns a Detection whose onset frames count from the
    recording's frame 0.
    """
    first = settings.first_frames
    frames = stack[first : len(stack) - settings.last_frames].astype(np.float32)
    tissue = tissue_mask(resting_brightness(stack, settings), electrode, settings)
    d = bleach_corrected(frames, settings)
    noise = pixel_noise(d, tissue)
    d = despiked(d, tissue, settings)
    z, before = z_movie(d, tissue, settings)
    searched = z.shape[0] - settings.frames(settings.end_trim_ms)
    last_onset = before + searched - 1
    (up, up_z), (down, down_z) = signed_regions(z, before, settings)
    result = Detection(counted(up, up_z, settings, last_onset), searched_frames=max(searched, 0), first_onset=before + first,
                       tissue=tissue, peak_z=z.max(0) if len(z) else np.zeros(tissue.shape), first_frame=first,
                       pixel_noise=noise)
    if settings.sign_flip:
        result.sign_flipped = counted(down, down_z, settings, last_onset)
    del z
    if settings.time_reversed:
        zr, _ = z_movie(d[::-1].copy(), tissue, settings)
        (back, back_z), _ = signed_regions(zr, before, settings)
        result.time_reversed = counted(back, back_z, settings, last_onset)
        del zr
    for found in (result.events, result.sign_flipped, result.time_reversed):
        if found is not None and len(found):
            found[:, 0] += first
    if keep_dff:
        result.dff = d
    return result
