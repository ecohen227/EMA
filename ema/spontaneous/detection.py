"""The spontaneous-event detector, step by step.

1. dF/F of every pixel against a polynomial fitted over time (bleaching),
   then a running median over a few frames (camera spikes).
2. A matched filter in time: the event shape (the template), fitted with a
   straight-line baseline at every frame.
3. A matched filter in space: a Gaussian over the tissue only.
4. Each filtered frame's median over the tissue is subtracted (the
   field-wide signal).
5. The strength z = (output − its median) ÷ (1.4826 × its median absolute
   deviation), pixel by pixel: how many times the noise the output rises.
6. An event is a connected region of z ≥ the region threshold whose maximum
   reaches the event threshold, placed at that maximum.
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
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

BLEACH_CHUNK = 2048  # pixels corrected for bleaching at a time, which keeps the float64 intermediates small
ECHO_MIN_Z = 5.0  # regions weaker than this neither count nor veto (unless the event threshold is lower)
# Regions are connected through faces, edges and corners in time and space: these are the neighbours that come
# later in the movie (the other half are the same pairs seen from the other side).
LATER_NEIGHBOURS = [(dt, dr, dc) for dt in (0, 1) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dt, dr, dc) > (0, 0, 0)]


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
    corrected = np.empty(values.shape, np.float32)
    for start in range(0, values.shape[1], BLEACH_CHUNK):
        part = slice(start, start + BLEACH_CHUNK)
        corrected[:, part] = values[:, part] / (basis @ coefficients[:, part]) - 1
    return corrected.reshape(frames.shape)


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


def median_of_rows(values, overwrite=False):
    """The median of each row of a 2-D array: the same numbers as np.median(values, axis=1), but faster.

    With `overwrite`, `values` is reordered in place instead of copied.
    """
    part = values if overwrite else values.copy()
    middle = part.shape[1] // 2
    if part.shape[1] % 2:
        part.partition(middle, axis=1)
        found = part[:, middle].copy()
    else:
        part.partition((middle - 1, middle), axis=1)
        found = (part[:, middle - 1] + part[:, middle]) / 2
    found[np.isnan(part).any(axis=1)] = np.nan
    return found


def pixel_noise(d, tissue):
    """The median over the tissue of each pixel's robust SD over time (1.4826 × median absolute deviation), in %."""
    if not tissue.any():
        return np.nan
    pixels = np.ascontiguousarray(d[:, tissue].T)  # one row per pixel
    pixels -= median_of_rows(pixels)[:, None]
    np.abs(pixels, out=pixels)
    return float(np.median(median_of_rows(pixels, overwrite=True)) * 1.4826 * 100)


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
        out = ndimage.gaussian_filter(movie, (0, sigma, sigma), mode="constant", truncate=3.0)
        out /= np.maximum(weight, 1e-3)
    else:
        out = movie.copy()
    if settings.remove_field:
        out -= median_of_rows(out[:, tissue], overwrite=True)[:, None, None]
    return out


def zscore(movie, tissue):
    """(value − median) ÷ (1.4826 × median absolute deviation) per pixel, from every second frame; 0 off the tissue."""
    flat = movie.reshape(len(movie), -1)
    inside = np.flatnonzero(tissue.ravel())
    sample = np.ascontiguousarray(flat[::2][:, inside].T)  # one row per tissue pixel
    center = np.zeros(flat.shape[1], movie.dtype)
    center[inside] = median_of_rows(sample)
    sample -= center[inside][:, None]
    np.abs(sample, out=sample)
    spread = np.ones(flat.shape[1], movie.dtype)
    spread[inside] = median_of_rows(sample, overwrite=True) * 1.4826
    flat -= center
    flat /= np.maximum(spread, 1e-12)
    flat[:, ~tissue.ravel()] = 0
    return movie


def connected(mask):
    """(flat index, region number) of every True pixel of a 3-D mask, its regions connected through faces, edges and
    corners. Regions are numbered from 1 in the order their first pixel comes in the movie, as ndimage.label numbers
    them; only the True pixels are visited, which is much faster when they are few."""
    flat = mask.ravel()
    inside = np.flatnonzero(flat)
    if not inside.size:
        return inside, inside
    frames, rows, cols = mask.shape
    t, rest = np.divmod(inside, rows * cols)
    r, c = np.divmod(rest, cols)
    starts, ends = [], []
    for dt, dr, dc in LATER_NEIGHBOURS:
        within = np.flatnonzero((t + dt < frames) & (r + dr >= 0) & (r + dr < rows) & (c + dc >= 0) & (c + dc < cols))
        neighbour = inside[within] + (dt * rows + dr) * cols + dc
        both = flat[neighbour]
        starts.append(within[both])
        ends.append(np.searchsorted(inside, neighbour[both]))
    starts, ends = np.concatenate(starts), np.concatenate(ends)
    graph = coo_matrix((np.ones(len(starts), np.int8), (starts, ends)), shape=(len(inside), len(inside)))
    _, region = connected_components(graph, directed=False)
    _, first = np.unique(region, return_index=True)  # where each region starts in the movie
    number = np.empty(len(first), np.int64)
    number[np.argsort(first)] = np.arange(1, len(first) + 1)
    return inside, number[region]


def regions(z, low, offset, sign=1):
    """Connected regions of sign × z ≥ low: (onset frame, row, column) of each region's maximum, and that maximum.

    The onset is the frame `offset` frames after the start of the template window.
    """
    inside, label_of = connected(z >= low if sign > 0 else z <= -low)
    if not inside.size:
        return np.zeros((0, 3)), np.zeros(0)
    value = sign * z.ravel()[inside]
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
    down = regions(z, settings.region_z, before, sign=-1)
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
    del frames
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
