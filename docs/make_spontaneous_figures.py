"""The figures of the spontaneous-event documentation, from the sample unstimulated recording with two events planted in it.

    python docs/make_spontaneous_figures.py [folder with the sample recordings]

The sample recording (2P_input_output/no6.tif) holds no event, so two Gaussian
events with the dLight time course are planted in a copy of it, as the
study's sensitivity check does; everything else in the figures is the real
recording. The copy is written to a temporary folder; the sample is only read.
"""

import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import tifffile  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

from ema.recordings import load_stack  # noqa: E402
from ema.roi_selection import RoiSettings, detect_folder  # noqa: E402
from ema.spontaneous.detection import (  # noqa: E402
    bleach_corrected,
    despiked,
    detect,
    kernel,
    resting_brightness,
    space_filter,
    template,
    tissue_mask,
    z_movie,
)
from ema.spontaneous.measures import TRACE_BEFORE, event_trace, measure_events, peak_map  # noqa: E402
from ema.spontaneous.settings import DetectorSettings  # noqa: E402

DOCS = Path(__file__).parent
FIGURES = DOCS / "figures"
SAMPLE = DOCS.parents[1] / "EMA_V3_handoff_2026-11-14" / "EMA_V3_handoff_2026-11-14" / "4_sample_data" / "recordings"
PLANTED = [(560, 34, 92, 0.04, 9.4), (1180, 98, 70, 0.03, 7.5)]  # onset frame, row, column, peak dF/F, σ in pixels


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
    steps(stack, electrode, s, found)
    event_figure(found, events, s)


def steps(stack, electrode, s, found):
    """The template, one pixel's dF/F against the pooled trace, z over time, and each pixel's largest z."""
    frames = stack[s.first_frames : len(stack) - s.last_frames].astype(np.float32)
    tissue = tissue_mask(resting_brightness(stack, s), electrode, s)
    d = despiked(bleach_corrected(frames, s), tissue, s)
    z, before = z_movie(d.copy(), tissue, s)
    frame, row, col, _ = found.events[0]
    onset = int(frame) - s.first_frames
    figure, axes = plt.subplots(2, 2, figsize=(11, 7.5), layout="constrained")

    shape, before = template(s)
    t = (np.arange(len(shape)) - before) * s.frame_ms
    plain = kernel(t, s.decay_ms, s.rise_ms)
    axes[0, 0].plot(t, plain / np.sqrt((plain**2).sum()), color="gray", label="dLight shape (12 ms rise, 200 ms decay)")
    axes[0, 0].plot(t, shape, color="tab:blue", label="template: the shape minus its best straight line")
    axes[0, 0].axhline(0, color="black", linewidth=0.5)
    axes[0, 0].set(xlabel="ms from the onset", ylabel="weight (unit length)", title="1  The time filter (template)")
    axes[0, 0].legend(fontsize=8)

    window = slice(onset - 100, onset + 250)
    ms = (np.arange(window.start, window.stop) - onset) * s.frame_ms
    pooled = space_filter(d[window], tissue, s)[:, int(row), int(col)]
    axes[0, 1].plot(ms, d[window, int(row), int(col)] * 100, color="lightgray", linewidth=0.8, label="one pixel (16 µm)")
    axes[0, 1].plot(ms, pooled * 100, color="tab:blue", label="pooled by the 128 µm Gaussian")
    axes[0, 1].axvline(0, color="gray", linestyle="--", linewidth=1)
    axes[0, 1].set(xlabel="ms from the onset", ylabel="dF/F (%)", title="2  One pixel is noisier than an event; pooling helps")
    axes[0, 1].legend(fontsize=8)

    zt = z[:, int(row), int(col)]
    zms = (np.arange(len(zt)) + before - onset) * s.frame_ms
    axes[1, 0].plot(zms / 1000, zt, color="tab:purple", linewidth=0.8)
    axes[1, 0].axhline(s.event_z, color="tab:red", linestyle="--", label=f"event threshold θ = {s.event_z:g}")
    axes[1, 0].axhline(s.region_z, color="tab:orange", linestyle=":", label=f"region threshold = {s.region_z:g}")
    axes[1, 0].set(xlabel="s from the event's onset", ylabel="z", title="3  z at the event's pixel over the recording")
    axes[1, 0].legend(fontsize=8)

    image = axes[1, 1].imshow(np.where(tissue, z.max(0), np.nan), cmap="magma", vmin=0, vmax=2 * s.event_z)
    figure.colorbar(image, ax=axes[1, 1], label="largest z", shrink=0.85)
    if electrode is not None and electrode.any():
        axes[1, 1].contour(electrode, [0.5], colors="cyan", linewidths=1)
    for n, (_, r, c, zv) in enumerate(found.events, start=1):
        axes[1, 1].add_patch(Circle((c, r), 7, fill=False, color="white"))
        axes[1, 1].annotate(f"{n}: z {zv:.0f}", (c + 8, r - 8), color="white", fontsize=8)
    axes[1, 1].set(xticks=[], yticks=[], title="4  Each pixel's largest z; events circled")
    figure.savefig(FIGURES / "spontaneous_steps.png", dpi=120)
    plt.close(figure)
    print("saved spontaneous_steps.png")


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
    axes[0].set(xticks=[], yticks=[], title=f"Peak map: width σ {e['width']:.0f} µm, fitted peak {e['fitted peak']:.1f} %\n"
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
    figure.savefig(FIGURES / "spontaneous_event.png", dpi=120)
    plt.close(figure)
    print("saved spontaneous_event.png")


if __name__ == "__main__":
    main()
