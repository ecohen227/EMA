"""The figures of the spontaneous-event documentation, from the sample unstimulated recording with two events planted in it.

    python docs/make_spontaneous_figures.py [folder with the sample recordings]

The sample recording (2P_input_output/no6.tif) holds no event, so two Gaussian
events with the dLight time course are planted in a copy of it, as the
study's sensitivity check does; everything else in the figures is the real
recording. The copy is written to a temporary folder; the sample is only read.

One figure per step of "How the detector works" (detector_*.png), and the
figure of how an event is measured (spontaneous_event.png).
"""

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import tifffile  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

from ema.recordings import load_stack  # noqa: E402
from ema.roi_selection import RoiSettings, detect_folder  # noqa: E402
from ema.spontaneous.detection import (  # noqa: E402
    bleach_corrected,
    despiked,
    detect,
    kernel,
    resting_brightness,
    template,
    time_filter,
    tissue_mask,
    zscore,
)
from ema.spontaneous.measures import TRACE_BEFORE, event_trace, measure_events, peak_map  # noqa: E402
from ema.spontaneous.settings import DetectorSettings  # noqa: E402
from scipy import ndimage  # noqa: E402

DOCS = Path(__file__).parent
FIGURES = DOCS / "figures"
SAMPLE = DOCS.parents[1] / "EMA_V3_handoff_2026-11-14" / "EMA_V3_handoff_2026-11-14" / "4_sample_data" / "recordings"
PLANTED = [(560, 34, 92, 0.04, 9.4), (1180, 98, 70, 0.03, 7.5)]  # onset frame, row, column, peak dF/F, σ in pixels
PIXEL, POOLED, ZCOLOUR = "lightgray", "tab:blue", "tab:purple"


def planted_example(recordings, folder, planted=PLANTED, name="no6.tif"):
    """Write a copy of the sample's no6.tif with planted events into `folder`; return (centre, electrode) of the sample.

    `planted` lists (onset frame, row, column, peak dF/F, σ in pixels).
    """
    source = recordings / "2P_input_output"
    roi = detect_folder(source, RoiSettings())
    stack = load_stack(source / "no6.tif").astype(np.float32)
    t_ms = np.arange(len(stack)) * DetectorSettings().frame_ms
    rows, cols = np.indices(stack.shape[1:])
    added = np.zeros_like(stack)
    for onset, row, col, peak, sigma in planted:
        shape = np.exp(-((cols - col) ** 2 + (rows - row) ** 2) / (2 * sigma**2)).astype(np.float32)
        added += peak * kernel(t_ms - onset * DetectorSettings().frame_ms, 200.0, 12.0).astype(np.float32)[:, None, None] * shape
    movie = np.round(stack * (1 + added)).clip(0, 65535).astype(np.uint16)
    folder.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(folder / name, np.concatenate([movie[:1], movie]))  # EMA drops the first frame of a file
    return tuple(roi.center), roi.electrode


@dataclass
class Steps:
    """Everything the detector computes on one recording, step by step (as in ema.spontaneous.detection.detect)."""

    s: DetectorSettings
    frames: np.ndarray  # F: the searched frames
    f0: np.ndarray
    tissue: np.ndarray
    raw: np.ndarray  # dF/F before the spike filter
    d: np.ndarray  # dF/F after it
    shape: np.ndarray  # h
    before: int  # B
    y: np.ndarray  # time-filtered
    pooled: np.ndarray  # space-filtered, before the field-wide signal is removed
    field: np.ndarray  # the field-wide signal of each output frame
    z: np.ndarray

    @classmethod
    def of(cls, stack, electrode, s):
        frames = stack[s.first_frames : len(stack) - s.last_frames].astype(np.float32)
        f0 = resting_brightness(stack, s)
        tissue = tissue_mask(f0, electrode, s)
        raw = bleach_corrected(frames, s)
        d = despiked(raw.copy(), tissue, s)
        shape, before = template(s)
        y = time_filter(d, shape)
        sigma = s.pixels(s.blur_um)
        weight = ndimage.gaussian_filter(tissue.astype(np.float32), sigma, mode="constant", truncate=3.0)
        pooled = ndimage.gaussian_filter(y, (0, sigma, sigma), mode="constant", truncate=3.0) / np.maximum(weight, 1e-3)
        field = np.median(pooled[:, tissue], axis=1)
        z = zscore(pooled - field[:, None, None], tissue)
        return cls(s, frames, f0, tissue, raw, d, shape, before, y, pooled, field, z)

    def output_frame(self, recording_frame):
        """The frame of the filtered movies whose onset is this frame of the recording."""
        return int(recording_frame) - self.s.first_frames - self.before


def main():
    recordings = (Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE).resolve()
    FIGURES.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp()) / "Slice 1" / "input output"
    center, electrode = planted_example(recordings, folder)
    s = DetectorSettings()
    stack = load_stack(folder / "no6.tif")
    found = detect(stack, electrode, s)
    events = measure_events(found, s, center, electrode)
    print(f"{len(found.events)} events found:", found.events.round(1).tolist())
    steps = Steps.of(stack, electrode, s)
    event = found.events[0]
    for draw in (tissue_figure, dff_figure, time_filter_figure, space_filter_figure, strength_figure, regions_figure,
                 echoes_figure):
        draw(steps, event, electrode, found)
    event_figure(found, events, s)


def save(figure, name):
    figure.savefig(FIGURES / name, dpi=120)
    plt.close(figure)
    print("saved", name)


def ms_from(frames, onset_frame, s):
    return (np.asarray(frames) - onset_frame) * s.frame_ms


def tissue_figure(st, event, electrode, found):
    figure, axes = plt.subplots(1, 2, figsize=(9, 3.9), layout="constrained")
    shown = axes[0].imshow(st.f0, cmap="gray")
    figure.colorbar(shown, ax=axes[0], label="F0 (counts)", shrink=0.85)
    if electrode is not None and electrode.any():
        axes[0].contour(electrode, [0.5], colors="cyan", linewidths=1)
    axes[0].set(xticks=[], yticks=[], title="Resting brightness F0, electrode in cyan")
    axes[1].imshow(st.f0, cmap="gray")
    axes[1].imshow(np.where(st.tissue, np.nan, 1.0), cmap=ListedColormap(["tab:red"]), alpha=0.45, vmin=0, vmax=1)
    axes[1].set(xticks=[], yticks=[], title=f"Tissue searched; red: blocks of {st.s.block_px} × {st.s.block_px} pixels "
                                            "left out", )
    axes[1].title.set_fontsize(9)
    save(figure, "detector_1_tissue.png")


def dff_figure(st, event, electrode, found):
    s, row, col = st.s, int(event[1]), int(event[2])
    count = len(st.frames)
    basis = np.vander(np.linspace(-1, 1, count), s.bleach_order + 1)
    trace = st.frames[:, row, col].astype(float)
    curve = basis @ np.linalg.lstsq(basis, trace, rcond=None)[0]
    seconds = (np.arange(count) + s.first_frames) * s.frame_ms / 1000
    figure, axes = plt.subplots(1, 2, figsize=(11, 3.6), layout="constrained", gridspec_kw={"width_ratios": [1.4, 1]})
    axes[0].plot(seconds, trace, color=PIXEL, linewidth=0.7, label="F: one pixel's brightness")
    axes[0].plot(seconds, curve, color="tab:red", label=f"P: its polynomial of order {s.bleach_order}")
    axes[0].set(xlabel="s", ylabel="brightness (counts)", title="Bleaching: the slow fall that P follows")
    axes[0].legend(fontsize=8)
    t = st.output_frame(event[0]) + st.before
    window = slice(t - 60, t + 60)
    ms = ms_from(np.arange(window.start, window.stop), t, s)
    axes[1].plot(ms, st.raw[window, row, col] * 100, color=PIXEL, linewidth=0.9, label="dF/F = F ÷ P − 1")
    axes[1].plot(ms, st.d[window, row, col] * 100, color=POOLED, linewidth=1, label=f"after the {s.despike_frames}-frame median")
    axes[1].axvline(0, color="gray", linestyle="--", linewidth=1)
    axes[1].set(xlabel="ms from the planted event's onset", ylabel="dF/F (%)", title="dF/F, and the spike filter")
    axes[1].legend(fontsize=8)
    save(figure, "detector_2_dff.png")


def time_filter_figure(st, event, electrode, found):
    s = st.s
    j = np.arange(len(st.shape))
    t = (j - st.before) * s.frame_ms
    k = kernel(t, s.decay_ms, s.rise_ms)
    line = np.column_stack([np.ones_like(k), j])
    fitted = line @ np.linalg.lstsq(line, k, rcond=None)[0]
    figure, axes = plt.subplots(1, 2, figsize=(11, 3.8), layout="constrained")
    axes[0].plot(t, k, color="gray", label="k: the dLight event shape")
    axes[0].plot(t, fitted, color="gray", linestyle="--", label="its best straight line")
    axes[0].plot(t, k - fitted, color=POOLED, label="h̃ = k − the line")
    axes[0].axhline(0, color="black", linewidth=0.5)
    axes[0].set(xlabel="ms from the onset", ylabel="weight", title="The event shape, before and after its line is removed")
    axes[0].legend(fontsize=8)
    row, col = int(event[1]), int(event[2])
    onset = st.output_frame(event[0])
    window = np.arange(onset - 150, onset + 250)
    ms = ms_from(window, onset, s)
    noise = 1.4826 * np.median(np.abs(st.y[:, row, col] - np.median(st.y[:, row, col])))
    axes[1].plot(ms, st.y[window, row, col] / noise, color=POOLED, linewidth=1, label="y at the event's pixel")
    axes[1].axvline(0, color="gray", linestyle="--", linewidth=1, label="the planted event's onset")
    axes[1].axhline(0, color="black", linewidth=0.5)
    axes[1].set(xlabel="ms from the onset (frame t + B)", ylabel="y (× its own noise)",
                title="y at the event's pixel: alone, the event hardly stands out")
    axes[1].legend(fontsize=8)
    save(figure, "detector_3_time_filter.png")


def space_filter_figure(st, event, electrode, found):
    s, row, col = st.s, int(event[1]), int(event[2])
    onset = st.output_frame(event[0])
    figure, axes = plt.subplots(1, 3, figsize=(13, 3.7), layout="constrained", gridspec_kw={"width_ratios": [1, 1, 1.5]})
    for ax, image, title in ((axes[0], st.y[onset], "y at the onset: one pixel at a time"),
                             (axes[1], st.pooled[onset], f"g: pooled over σ = {s.blur_um:g} µm")):
        inside = image[st.tissue]
        spread = 1.4826 * np.median(np.abs(inside - np.median(inside)))
        shown = ax.imshow(np.where(st.tissue, (image - np.median(inside)) / spread, np.nan), cmap="magma", vmin=-2, vmax=6)
        ax.add_patch(Circle((col, row), 12, fill=False, color="white", linestyle=":"))
        ax.set(xticks=[], yticks=[], title=title)
        figure.colorbar(shown, ax=ax, label="× the frame's spread", shrink=0.8)
    window = np.arange(onset - 150, onset + 250)
    ms = ms_from(window, onset, s)
    for values, colour, label in ((st.y, PIXEL, "y: one pixel"), (st.pooled, POOLED, "g: pooled")):
        trace = values[:, row, col]
        noise = 1.4826 * np.median(np.abs(trace - np.median(trace)))
        axes[2].plot(ms, (trace[window] - np.median(trace)) / noise, color=colour, linewidth=1, label=label)
    axes[2].axvline(0, color="gray", linestyle="--", linewidth=1)
    axes[2].set(xlabel="ms from the onset", ylabel="× its own noise", title="At the event's pixel, pooling lifts the event "
                                                                              "out of the noise")
    axes[2].legend(fontsize=8)
    save(figure, "detector_4_space_filter.png")


def strength_figure(st, event, electrode, found):
    s, row, col = st.s, int(event[1]), int(event[2])
    onset = st.output_frame(event[0])
    figure, axis = plt.subplots(figsize=(9, 3.4), layout="constrained")
    zt = st.z[:, row, col]
    axis.plot(ms_from(np.arange(len(zt)), onset, s) / 1000, zt, color=ZCOLOUR, linewidth=0.8)
    axis.axhline(s.event_z, color="tab:red", linestyle="--", label=f"event threshold, {s.event_z:g} × noise")
    axis.axhline(s.region_z, color="tab:orange", linestyle=":", label=f"region threshold, {s.region_z:g} × noise")
    axis.set(xlabel="s from the event's onset", ylabel="z (× noise)",
             title="z at the event's pixel, over the whole recording: noise stays near 0, the event reaches 23")
    axis.title.set_fontsize(10)
    axis.legend(fontsize=8)
    save(figure, "detector_6_strength.png")


def regions_figure(st, event, electrode, found):
    s, row, col = st.s, int(event[1]), int(event[2])
    onset = st.output_frame(event[0])
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    frame = np.where(st.tissue, st.z[onset], np.nan)
    shown = axes[0].imshow(frame, cmap="magma", vmin=-3, vmax=2 * s.event_z)
    axes[0].contour(st.z[onset] >= s.region_z, [0.5], colors="white", linewidths=1)
    axes[0].plot(col, row, "+", color="cyan", markersize=12, markeredgewidth=2)
    axes[0].set(xticks=[], yticks=[], title=f"z at the onset frame; white: z ≥ {s.region_z:g}, cyan +: the maximum")
    axes[0].title.set_fontsize(9)
    figure.colorbar(shown, ax=axes[0], label="z (× noise)", shrink=0.85)
    shown = axes[1].imshow(np.where(st.tissue, st.z.max(0), np.nan), cmap="magma", vmin=0, vmax=2 * s.event_z)
    figure.colorbar(shown, ax=axes[1], label="largest z (× noise)", shrink=0.85)
    if electrode is not None and electrode.any():
        axes[1].contour(electrode, [0.5], colors="cyan", linewidths=1)
    for n, (_, r, c, zv) in enumerate(found.events, start=1):
        axes[1].add_patch(Circle((c, r), 7, fill=False, color="white"))
        axes[1].annotate(f"{n}: {zv:.0f} × noise", (c + 8, r - 8), color="white", fontsize=8)
    axes[1].set(xticks=[], yticks=[], title="Each pixel's largest z; the events found, circled")
    axes[1].title.set_fontsize(9)
    save(figure, "detector_7_regions.png")


def echoes_figure(st, event, electrode, found):
    s, row, col = st.s, int(event[1]), int(event[2])
    onset = st.output_frame(event[0])
    reach = s.frames(s.echo_ms)
    window = np.arange(max(onset - 2 * reach, 0), min(onset + 2 * reach, len(st.z)))
    ms = ms_from(window, onset, s)
    zt = st.z[window, row, col]
    figure, axis = plt.subplots(figsize=(9, 3.6), layout="constrained")
    axis.axvspan(-reach * s.frame_ms, reach * s.frame_ms, color="tab:orange", alpha=0.12,
                 label=f"close in time: within {s.echo_ms:g} ms")
    axis.plot(ms, zt, color=ZCOLOUR, linewidth=1, label="z at the event's pixel")
    dips = zt <= -s.region_z
    axis.fill_between(ms, zt, -s.region_z, where=dips, color="tab:cyan", alpha=0.6, label="dips (regions of −z)")
    axis.axhline(s.region_z, color="tab:orange", linestyle=":", linewidth=1)
    axis.axhline(-s.region_z, color="tab:orange", linestyle=":", linewidth=1)
    axis.axhline(0, color="black", linewidth=0.5)
    axis.set(xlabel="ms from the event's onset", ylabel="z (× noise)",
             title="An event and its echoes: the dips before and after it are weaker and close, so they do not count")
    axis.title.set_fontsize(10)
    axis.legend(fontsize=8, loc="upper right")
    save(figure, "detector_8_echoes.png")


def event_figure(found, events, s):
    """How one event is measured: its peak map with the fitted half-maximum circle, and its pooled trace."""
    frame, row, col, z = found.events[0]
    e = events[0]
    onset = int(frame) - found.first_frame
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", gridspec_kw={"width_ratios": [1, 1.6]})
    image = peak_map(found, onset, int(row), int(col), s) * 100
    shown = axes[0].imshow(image, cmap="viridis")
    figure.colorbar(shown, ax=axes[0], label="dF/F (%)", shrink=0.85)
    half = np.sqrt(2 * np.log(2)) * e["width"] / s.pixel_um
    axes[0].add_patch(Circle((e["x"] / s.pixel_um, e["y"] / s.pixel_um), half, fill=False, color="white"))
    axes[0].add_patch(Circle((e["x"] / s.pixel_um, e["y"] / s.pixel_um), s.pixels(s.fit_radius_um), fill=False, color="white",
                             linestyle=":"))
    axes[0].set(xticks=[], yticks=[], title=f"Peak map: width {e['width']:.0f} µm, fitted peak {e['fitted peak']:.1f} %\n"
                                          "solid: half maximum; dotted: the fit radius")
    trace = event_trace(found, s, onset, int(row), int(col))
    times = (np.arange(len(trace)) - TRACE_BEFORE) * s.frame_ms
    shown_trace = (trace - np.median(trace[: TRACE_BEFORE - 10])) * 100
    axes[1].plot(times, shown_trace, color="tab:blue", linewidth=1)
    axes[1].axvline(0, color="gray", linestyle="--", linewidth=1, label="detected onset")
    peak_ms = e["time to peak"]
    axes[1].axvline(peak_ms, color="tab:green", linewidth=1, label=f"peak ({e['local peak']:.2f} %, local)")
    axes[1].axvline(peak_ms + e["half-decay"], color="tab:red", linewidth=1, label=f"half-decay {e['half-decay']:.0f} ms")
    axes[1].set(xlabel="ms from the onset", ylabel="pooled dF/F (%)",
                title=f"Pooled trace: rise 10–90 % {e['rise 10-90']:.0f} ms, half-decay {e['half-decay']:.0f} ms")
    axes[1].legend(fontsize=8)
    save(figure, "spontaneous_event.png")


if __name__ == "__main__":
    main()
