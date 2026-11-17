"""Draws the figures of the documentation from real recordings.

    python docs/make_figures.py [folder with the sample recordings]

The folder must hold `2P_input_output/300uA.tif` and `2P_input_output/no6.tif`.
The figures are saved in docs/figures. Every figure calls the same functions as the program, so the
pictures show what the program really does.
"""

import sys
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle
from scipy import ndimage

from ema.recordings import load_stack
from ema.roi_selection import RoiSettings, detect_folder, find_electrode, find_roi_center, response_map, roi_trace
from ema.roi_selection.detection import _looks_like_electrode, baseline_image, peak_frame

DOCS = Path(__file__).parent
FIGURES = DOCS / "figures"
HANDOFF = DOCS.parents[1] / "EMA_V3_handoff_2026-11-14" / "EMA_V3_handoff_2026-11-14"
SAMPLE_DATA = HANDOFF / "4_sample_data" / "recordings"
SETTINGS = RoiSettings()
BASELINE_COLOR, SEARCH_COLOR, PEAK_COLOR, ELECTRODE_COLOR = "0.8", "#fde9c9", "#2a9d8f", "cyan"

plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "figure.dpi": 150, "savefig.bbox": "tight"})


def save(figure, name):
    figure.savefig(FIGURES / name)
    plt.close(figure)
    print("saved", name)


def show(axes, image, title, colormap="inferno", **options):
    """An image without axis ticks."""
    picture = axes.imshow(image, cmap=colormap, interpolation="nearest", **options)
    axes.set_title(title)
    axes.set_xticks([])
    axes.set_yticks([])
    return picture


def outline(axes, mask, color=ELECTRODE_COLOR):
    if mask.any():
        axes.contour(mask, [0.5], colors=color, linewidths=1.2)


def circle(axes, center, radius, color="white", **options):
    axes.add_patch(Circle(center, radius, fill=False, edgecolor=color, linewidth=1.5, **options))


def shade_windows(axes):
    axes.axvspan(*SETTINGS.baseline_frames, color=BASELINE_COLOR, label="Baseline window")
    axes.axvspan(*SETTINGS.search_frames, color=SEARCH_COLOR, label="Response search window")


# ---------------------------------------------------------------------------
# The procedure
# ---------------------------------------------------------------------------


def procedure_roi(stack):
    f0 = baseline_image(stack, SETTINGS)
    peak = peak_frame(stack, SETTINGS)
    first, last = peak - SETTINGS.peak_frames_before, peak + SETTINGS.peak_frames_after
    at_peak = stack[first:last].mean(axis=0)
    response = response_map(stack, SETTINGS)
    smooth = ndimage.gaussian_filter(response, SETTINGS.smoothing_px)
    center, _ = find_roi_center(response, SETTINGS)

    figure, axes = plt.subplots(1, 5, figsize=(15, 3.1), width_ratios=[1.5, 1, 1, 1, 1], layout="constrained")
    shade_windows(axes[0])
    axes[0].axvspan(first, last, color=PEAK_COLOR, label="Frames averaged at the peak")
    axes[0].plot(stack.mean(axis=(1, 2)), color="black", linewidth=1)
    axes[0].set(xlim=(0, 350), xlabel="Frame", ylabel="Mean brightness of the image", title="1  Find the peak frame")
    axes[0].legend(fontsize=7, loc="upper right", framealpha=1)
    show(axes[1], f0, "2  Baseline image (F0)", "gray")
    show(axes[2], at_peak, "3  Image at the peak", "gray", vmin=f0.min(), vmax=at_peak.max())
    show(axes[3], response * 100, "4  Response map (dF/F, %)")
    picture = show(axes[4], smooth * 100, "5  Smooth, take the maximum")
    axes[4].plot(*center, "+", color="white", markersize=12)
    circle(axes[4], center, SETTINGS.roi_radius_px)
    figure.colorbar(picture, ax=axes[4], fraction=0.046, label="dF/F (%)")
    save(figure, "procedure_roi.png")


def procedure_electrode(f0, center):
    surroundings = ndimage.median_filter(f0, size=SETTINGS.electrode_surround_px)
    dark = ndimage.binary_opening(f0 < SETTINGS.electrode_threshold * surroundings)
    shapes, count = ndimage.label(dark)
    y, x = np.indices(f0.shape)
    distance = np.hypot(x - center[0], y - center[1])
    electrode = find_electrode(f0, center, SETTINGS)

    figure, axes = plt.subplots(1, 5, figsize=(15, 3.1), layout="constrained")
    show(axes[0], f0, "1  Baseline image (F0)", "gray")
    show(axes[1], surroundings, "2  Brightness of the surroundings", "gray", vmin=f0.min(), vmax=f0.max())
    picture = show(axes[2], f0 / surroundings, "3  Baseline ÷ surroundings", "gray", vmin=0.5, vmax=1.2)
    figure.colorbar(picture, ax=axes[2], fraction=0.046)
    verdict = np.full((*f0.shape, 3), 0.15)
    for number in range(1, count + 1):
        shape = shapes == number
        verdict[shape] = (0, 0.8, 0.8) if _looks_like_electrode(shape, distance, SETTINGS) else (0.9, 0.3, 0.3)
    show(axes[3], verdict, f"4  Dark shapes (below {SETTINGS.electrode_threshold:.2f})", None)
    axes[3].text(3, 122, "cyan: looks like the electrode\nred: too small, too far or not at the edge",
                 color="white", fontsize=6.5)
    show(axes[4], f0, "5  Tip back, gaps closed, grown", "gray")
    outline(axes[4], electrode)
    axes[4].plot(*center, "+", color="yellow", markersize=10)
    save(figure, "procedure_electrode.png")


# ---------------------------------------------------------------------------
# The settings
# ---------------------------------------------------------------------------


def setting_roi_radius(stack, response, center):
    figure, (left, right) = plt.subplots(1, 2, figsize=(9, 3.4), width_ratios=[1, 1.6], layout="constrained")
    show(left, response * 100, "ROI radius")
    for radius, color in ((10, "#8ecae6"), (20, "white"), (30, "#ffb703")):
        circle(left, center, radius, color)
        right.plot(
            roi_trace(stack, center, radius, SETTINGS),
            color="black" if color == "white" else color,
            linewidth=1,
            label=f"{radius} pixels ({radius * SETTINGS.pixel_size_um:.0f} µm)",
        )
    right.set(xlim=(60, 400), xlabel="Frame", ylabel="dF/F in the ROI (%)", title="Trace of each ROI")
    right.legend(frameon=False)
    save(figure, "setting_roi_radius.png")


def setting_smoothing(response):
    figure, axes = plt.subplots(1, 3, figsize=(9, 3.2), layout="constrained")
    for axis, width in zip(axes, (0, 2, 6)):
        center, _ = find_roi_center(response, replace(SETTINGS, smoothing_px=width))
        show(axis, ndimage.gaussian_filter(response, width) * 100, f"Smoothing {width} pixels\nmaximum at {center}")
        axis.plot(*center, "+", color="white", markersize=12)
        circle(axis, center, SETTINGS.roi_radius_px, linestyle=":")
    save(figure, "setting_smoothing.png")


def setting_timing(stack):
    peak = peak_frame(stack, SETTINGS)
    first, last = peak - SETTINGS.peak_frames_before, peak + SETTINGS.peak_frames_after
    brightness = stack.mean(axis=(1, 2))
    rest, top = brightness[10:95].mean(), brightness[:350].max()

    figure, axes = plt.subplots(figsize=(9, 3.4), layout="constrained")
    shade_windows(axes)
    axes.axvspan(first, last, color=PEAK_COLOR)
    axes.plot(brightness, color="black", linewidth=1)
    axes.axvline(peak, color="red", linestyle="--", linewidth=1)
    axes.text(52, top, "Baseline window\nframes 10 up to 95", ha="center", va="top", color="0.3", fontsize=8)
    axes.text(240, top, "Response search window\nframes 95 up to 300", ha="center", va="top", color="#b5651d", fontsize=8)
    axes.annotate("peak frame", (peak, rest + 0.9 * (top - rest)), (peak + 30, rest + 0.9 * (top - rest)),
                  color="red", arrowprops=dict(arrowstyle="->", color="red"), va="center", fontsize=8)
    axes.annotate("frames averaged around the peak\n(2 before, 8 from the peak on)",
                  ((first + last) / 2 + 3, rest + 0.55 * (top - rest)), (peak + 40, rest + 0.55 * (top - rest)),
                  color=PEAK_COLOR, arrowprops=dict(arrowstyle="->", color=PEAK_COLOR), va="center", fontsize=8)
    axes.set(xlim=(0, 350), xlabel="Frame", ylabel="Mean brightness of the image", title="Timing settings")
    save(figure, "setting_timing.png")


def setting_low_response(stimulated, unstimulated):
    figure, axes = plt.subplots(1, 2, figsize=(7, 3.3), layout="constrained")
    names = ("300uA.tif (stimulated)", "no6.tif (no stimulation)")
    for axis, stack, name in zip(axes, (stimulated, unstimulated), names):
        response = response_map(stack, SETTINGS)
        center, peak = find_roi_center(response, SETTINGS)
        warning = "  → warning" if peak * 100 < SETTINGS.low_response_percent else ""
        title = f"{name}\nresponse at the ROI: {peak * 100:.1f} %{warning}"
        picture = show(axis, response * 100, title, vmin=-5, vmax=100)
        circle(axis, center, SETTINGS.roi_radius_px)
    figure.colorbar(picture, ax=axes, fraction=0.03, label="dF/F (%)")
    save(figure, "setting_low_response.png")


def electrode_variants(f0, center, name, title, setting, values, unit=""):
    """The electrode mask for a few values of one setting, side by side."""
    figure, axes = plt.subplots(1, len(values), figsize=(3 * len(values), 2.6), layout="constrained")
    for axis, value in zip(axes, values):
        mask = find_electrode(f0, center, replace(SETTINGS, **{setting: value}))
        show(axis, f0, f"{title} {value}{unit}\n{mask.sum()} pixels masked", "gray")
        outline(axis, mask)
        axis.set(xlim=(-0.5, 90), ylim=(100, 40))
    save(figure, name)


def setting_electrode_shape(f0, center):
    mask = find_electrode(f0, center, SETTINGS)
    rows, columns = np.nonzero(mask)
    nearest = np.argmin(np.hypot(columns - center[0], rows - center[1]))
    length = np.hypot(np.ptp(columns), np.ptp(rows))
    label = dict(fontsize=8, bbox=dict(facecolor="black", alpha=0.6, edgecolor="none"))

    figure, axes = plt.subplots(figsize=(6, 4.2), layout="constrained")
    show(axes, f0, "What makes a dark shape the electrode", "gray")
    outline(axes, mask)
    axes.plot(*center, "+", color="yellow", markersize=12)
    axes.plot([columns[nearest], center[0]], [rows[nearest], center[1]], color="yellow", linewidth=1.5)
    axes.plot([columns.min(), columns.max()], [rows.min(), rows.max()], color="white", linestyle="--", linewidth=1)
    axes.axvline(0, color="#ff5d8f", linewidth=5)
    axes.text(3, 44, "Electrode enters from: left", color="#ff5d8f", **label)
    axes.text(3, rows.min() - 4, f"Length: {length:.0f} pixels (smallest allowed: 30)", color="white", **label)
    axes.text(3, rows.max() + 7, f"Area: {mask.sum()} pixels (smallest allowed: 100)", color=ELECTRODE_COLOR, **label)
    distance_note = "Distance to the centre of\nthe automatic ROI\n(greatest allowed: 40 pixels)"
    axes.text(center[0] + 4, center[1] + 2, distance_note, color="yellow", va="top", **label)
    axes.set(xlim=(-0.5, 127.5), ylim=(105, 35))
    save(figure, "setting_electrode_shape.png")


def main():
    data = Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE_DATA
    FIGURES.mkdir(exist_ok=True)
    stack = load_stack(data / "2P_input_output" / "300uA.tif")
    unstimulated = load_stack(data / "2P_input_output" / "no6.tif")
    detection = detect_folder(data / "2P_input_output", SETTINGS)
    f0, response, center = detection.baseline, detection.response, detection.center

    procedure_roi(stack)
    procedure_electrode(f0, center)
    setting_roi_radius(stack, response, center)
    setting_smoothing(response)
    setting_timing(stack)
    setting_low_response(stack, unstimulated)
    electrode_variants(f0, center, "setting_electrode_threshold.png", "Darkness threshold", "electrode_threshold", (0.80, 0.90, 0.97))
    electrode_variants(f0, center, "setting_electrode_surround.png", "Surroundings", "electrode_surround_px", (21, 31, 61), " pixels")
    electrode_variants(f0, center, "setting_electrode_grow.png", "Grow the mask by", "electrode_grow_px", (0, 1, 3), " pixels")
    setting_electrode_shape(f0, center)


if __name__ == "__main__":
    main()
