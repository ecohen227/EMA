"""The automatic ROI and electrode mask.

Plain functions on numpy arrays; nothing here needs the GUI. Positions are
(x, y) in pixels counted from 0: x is the column, y is the row.
"""

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from ..recordings import has_skip_word, is_no_stim, list_recordings, load_stack

# Raised when what the automatic detection finds changes, so that results that used it are measured again.
AUTOMATIC_VERSION = 2
TIP_PX = 15  # how far from the electrode's end nearest the ROI centre its thin tip is given back

IMAGE_EDGES = {
    "left": np.s_[:, 0],
    "right": np.s_[:, -1],
    "top": np.s_[0, :],
    "bottom": np.s_[-1, :],
}


# ---------------------------------------------------------------------------
# Response map and ROI
# ---------------------------------------------------------------------------


def baseline_image(stack, settings):
    """Mean of the baseline frames (F0): the resting brightness of every pixel."""
    start, stop = settings.baseline_frames
    if start >= len(stack):
        raise ValueError(f"The baseline window starts at frame {start}, but the recording has {len(stack)} frames.")
    return stack[start:stop].mean(axis=0)


def peak_frame(stack, settings):
    """The frame inside the search window where the whole image is brightest."""
    start, stop = settings.search_frames
    if start >= len(stack):
        raise ValueError(f"The search window starts at frame {start}, but the recording has {len(stack)} frames.")
    brightness = stack[start:stop].mean(axis=(1, 2))
    return start + int(np.argmax(ndimage.uniform_filter1d(brightness, size=5)))


def response_at(stack, frame, settings):
    """dF/F of every pixel around one frame: the mean of a few frames there / F0 - 1."""
    f0 = np.maximum(baseline_image(stack, settings), 1.0)  # never divide by zero
    first = max(frame - settings.peak_frames_before, 0)
    return stack[first : frame + settings.peak_frames_after].mean(axis=0) / f0 - 1


def response_map(stack, settings):
    """dF/F of every pixel at the peak of the response."""
    return response_at(stack, peak_frame(stack, settings), settings)


def find_roi_center(response, settings):
    """The pixel with the strongest response after smoothing, and the smoothed dF/F there."""
    smooth = ndimage.gaussian_filter(response, settings.smoothing_px)
    y, x = np.unravel_index(np.argmax(smooth), smooth.shape)
    return (int(x), int(y)), float(smooth[y, x])


def roi_mask(shape, center, radius):
    """True for the pixels of an image of this shape (rows, columns) that lie inside the circular ROI."""
    y, x = np.ogrid[: shape[0], : shape[1]]
    return (x - center[0]) ** 2 + (y - center[1]) ** 2 <= radius**2


def roi_trace(stack, center, radius, settings):
    """dF/F in percent of the mean brightness inside the ROI, for every frame."""
    mask = roi_mask(stack.shape[1:], center, radius)
    rows, columns = np.nonzero(mask)
    # Reading only the small square around the ROI is several times faster than reading whole frames.
    square = slice(rows.min(), rows.max() + 1), slice(columns.min(), columns.max() + 1)
    brightness = stack[:, square[0], square[1]].sum(axis=(1, 2), where=mask[square]) / mask.sum()
    start, stop = settings.baseline_frames
    return (brightness / brightness[start:stop].mean() - 1) * 100


# ---------------------------------------------------------------------------
# Electrode
# ---------------------------------------------------------------------------


def find_electrode(f0, center, settings):
    """Mask of the stimulating electrode in a baseline image.

    The electrode is opaque, so it shows as a dark shape that enters from one
    image edge and ends near the place of release. Of all dark shapes that
    look like that, the largest is the electrode. All False if there is none.
    """
    if not settings.find_electrode:
        return np.zeros(f0.shape, bool)

    surroundings = ndimage.median_filter(f0, size=settings.electrode_surround_px)
    dark_pixels = f0 < settings.electrode_threshold * surroundings
    dark = ndimage.binary_opening(dark_pixels)  # without specks of noise: shapes thinner than about 3 pixels
    shapes, count = ndimage.label(dark)

    y, x = np.indices(f0.shape)
    distance = np.hypot(x - center[0], y - center[1])
    candidates = [shapes == number for number in range(1, count + 1)]
    electrodes = [shape for shape in candidates if _looks_like_electrode(shape, distance, settings)]
    if not electrodes:
        return np.zeros(f0.shape, bool)

    electrode = max(electrodes, key=np.count_nonzero)
    electrode = _with_tip(electrode, dark_pixels, distance)
    electrode = ndimage.binary_fill_holes(_close_gaps(electrode))
    if settings.electrode_grow_px > 0:
        electrode = ndimage.binary_dilation(electrode, iterations=settings.electrode_grow_px)
    return electrode


def _with_tip(electrode, dark_pixels, distance):
    """The electrode with the dark pixels joined to it within TIP_PX of its end nearest the ROI centre.

    Clearing the specks of noise also clears the tip, which is only 1 or 2
    pixels wide. Nothing is given back elsewhere, so that thin dark lines
    along the image edge stay out.
    """
    tip = np.unravel_index(np.argmin(np.where(electrode, distance, np.inf)), electrode.shape)
    rows, columns = np.indices(electrode.shape)
    near_tip = np.hypot(rows - tip[0], columns - tip[1]) <= TIP_PX
    return ndimage.binary_propagation(electrode, mask=electrode | (dark_pixels & near_tip))


def _close_gaps(mask, width=2):
    """Bridge gaps and notches up to about twice this width. The padding keeps the image edge intact."""
    padded = np.pad(mask, width, mode="edge")
    return ndimage.binary_closing(padded, iterations=width)[width:-width, width:-width]


def _looks_like_electrode(shape, distance, settings):
    rows, columns = np.nonzero(shape)
    length = np.hypot(np.ptp(columns), np.ptp(rows))
    return bool(
        rows.size >= settings.electrode_min_area_px
        and length >= settings.electrode_min_length_px
        and distance[shape].min() <= settings.electrode_max_distance_px
        and touches_edge(shape, settings.electrode_edge)
    )


def touches_edge(mask, edge):
    edges = IMAGE_EDGES.values() if edge == "any" else [IMAGE_EDGES[edge]]
    return any(mask[index].any() for index in edges)


# ---------------------------------------------------------------------------
# A whole folder
# ---------------------------------------------------------------------------


@dataclass
class Detection:
    """What the automatic detection found in one recording folder."""

    files: list  # names of the recordings it used
    baseline: np.ndarray  # baseline image (F0) of their mean recording
    response: np.ndarray  # response map (dF/F) of their mean recording
    peak_frame: int  # frame of the peak of the response
    center: tuple  # automatic ROI centre (x, y)
    peak_response: float  # smoothed dF/F at the centre
    electrode: np.ndarray  # automatic electrode mask


def detection_files(paths, settings):
    """The recordings the automatic ROI is found from.

    These are the files named in the settings, if the folder has any of them.
    Otherwise every stimulated recording is used.
    """
    wanted = {name.lower() for name in settings.detection_files}
    named = [path for path in paths if path.stem.lower() in wanted]
    if named:
        return named
    return [path for path in paths if not is_no_stim(path) and not has_skip_word(path, settings.skip_words)]


def mean_recording(paths, load=load_stack):
    """The frame-by-frame mean of several recordings: one movie that stands for all of them."""
    first = load(paths[0])
    if len(paths) == 1:
        return first
    total = first.astype(np.float32)
    for path in paths[1:]:
        stack = load(path)
        if stack.shape != first.shape:
            names = ", ".join(path.name for path in paths)
            raise ValueError(f"{names} do not have the same size, so they cannot be averaged.")
        total += stack
    return total / len(paths)


def detect(stack, settings, files=()):
    """Find the ROI and the electrode in one recording, usually a mean recording."""
    baseline = baseline_image(stack, settings)
    peak = peak_frame(stack, settings)
    response = response_at(stack, peak, settings)
    center, peak_response = find_roi_center(response, settings)
    electrode = find_electrode(baseline, center, settings)
    return Detection(list(files), baseline, response, peak, center, peak_response, electrode)


def folder_mean(folder, settings, load=load_stack):
    """The recording the ROI of a folder is found on: the mean of its detection files.

    Returns the mean recording and the names of the files it was made from.
    """
    paths = detection_files(list_recordings(folder), settings)
    if not paths:
        raise ValueError("This folder has no stimulated recordings to find the ROI from.")
    return mean_recording(paths, load), [path.name for path in paths]


def detect_folder(folder, settings, load=load_stack):
    """Find the ROI and the electrode of one recording folder."""
    stack, files = folder_mean(folder, settings, load)
    return detect(stack, settings, files)
