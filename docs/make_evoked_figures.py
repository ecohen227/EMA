"""Draws the figures of the Evoked Analysis Configurator pages from real recordings.

    python docs/make_evoked_figures.py [folder with the sample recordings]

The folder must hold `2P_input_output/300uA.tif` and `no6.tif` (and the other recordings of that folder),
`11P_at_200uA/hi1.tif` and `11P_at_200uA/no2.tif`. Every number in the figures comes from the measuring
code of EMA (`ema.evoked`), with the built-in protocols.
"""

import sys
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle

from ema.evoked import measure
from ema.evoked.kinetics import crossing, kinetics, response_trace, smoothed
from ema.evoked.metrics import KINETIC_KEYS, SPATIAL_KEYS
from ema.evoked.presets import paired_pulse, pulse_train
from ema.evoked.protocol import Window
from ema.evoked.spatial import half_time, lorentzian, measure_spatial
from ema.evoked.traces import combine, correction_window, make_trace
from ema.recordings import load_stack
from ema.roi_selection import RoiSettings, detect_folder, roi_mask

DOCS = Path(__file__).parent
FIGURES = DOCS / "figures"
SAMPLE_DATA = DOCS.parents[1] / "EMA_V3_handoff_2026-11-14" / "EMA_V3_handoff_2026-11-14" / "4_sample_data" / "recordings"
TRACE, BASELINE, PEAK, STIMULUS, LEVEL, FIT = "#1f4e79", "#8d99ae", "#f4a261", "#d62828", "#2b2d42", "#c1121f"

plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "figure.dpi": 150, "savefig.bbox": "tight"})


def save(figure, name):
    figure.savefig(FIGURES / name)
    plt.close(figure)
    print("saved", name)


def roi_traces(folder, *names):
    """The ROI brightness of recordings of a folder, with the ROI found automatically."""
    detection = detect_folder(folder, RoiSettings())
    mask = roi_mask(detection.response.shape, detection.center, RoiSettings().roi_radius_px)
    return [load_stack(folder / name)[:, mask].mean(axis=1) for name in names]


def paired_sample(data, protocol):
    """ROI centre, electrode, and the corrected trace and movie of 300uA.tif (partner no6.tif, recorded after it)."""
    folder = data / "2P_input_output"
    detection = detect_folder(folder, RoiSettings())
    mask = roi_mask(detection.response.shape, detection.center, RoiSettings().roi_radius_px)
    stimulated, partner = (load_stack(folder / name).astype(np.float32) for name in ("300uA.tif", "no6.tif"))
    trace = make_trace(protocol, stimulated[:, mask].mean(axis=1), partner[:, mask].mean(axis=1))
    movie = combine(stimulated, np.maximum(partner, 1), False, correction_window(protocol))
    return detection.center, detection.electrode, trace, movie, stimulated[:, mask].mean(axis=1)


def shade(axes, window, color, label=None, low=0.0, high=1.0):
    axes.axvspan(window.start, window.end, ymin=low, ymax=high, color=color, alpha=0.3, lw=0, label=label)


def mark(axes, measurement, protocol, recording=None, labels=True):
    """Baseline levels, peaks and fits of a measurement."""
    for name, (window, level) in measurement.levels.items():
        axes.plot([window.start, window.end], [level, level], color=LEVEL, lw=2.5)
    for name, (frame, value) in measurement.peaks.items():
        axes.plot(frame, value, "o", color=LEVEL, ms=4)
        if labels:
            axes.annotate(name, (frame, value), (4, 4), textcoords="offset points", fontsize=8)
    for curve in measurement.fits.values():
        if curve is not None:
            first, values = curve
            axes.plot(first + np.arange(len(values)), values, "--", color=FIT, lw=1.3)


# ---------------------------------------------------------------------------
# Brightness: the paired-pulse protocol
# ---------------------------------------------------------------------------


def brightness_figure(data):
    protocol = paired_pulse()
    *_, trace, _, raw = paired_sample(data, protocol)
    result = measure(protocol, trace)
    values = result.values

    figure, (whole, zoom) = plt.subplots(1, 2, figsize=(12, 3.8), width_ratios=[1.6, 1], layout="constrained")
    whole.plot(raw, color="0.75", lw=1, label="300uA.tif as recorded")
    for axes in (whole, zoom):
        axes.plot(trace, color=TRACE, lw=1, label="corrected with no6.tif (measured)")
        for name in protocol.baselines:
            shade(axes, protocol.baselines[name], BASELINE, high=0.45)
        for pulse in protocol.pulses:
            shade(axes, pulse.peak, PEAK, low=0.55)
            axes.axvline(pulse.stimulus, color=STIMULUS, ls="--", lw=1)
        mark(axes, result, protocol)
        axes.set(xlabel="Frame", ylabel="ROI brightness (counts)")
    whole.set(xlim=(0, 1300), title="300uA.tif, corrected with no6.tif, with the 2P paired-pulse protocol")
    whole.legend(frameon=False, fontsize=8, loc="lower right")
    whole.text(0.98, 0.95, f"P1 response = {values['P1 response']:.1f} %\nP2 response = {values['P2 response']:.1f} %\n"
                           f"PPR = P2 response ÷ P1 response = {values['PPR']:.2f}\nTau = {values['Tau']:.0f} ms",
               transform=whole.transAxes, ha="right", va="top", fontsize=8.5, bbox=dict(fc="white", ec="0.8"))

    b1, (frame, p1) = values["B1"], result.peaks["P1"]
    zoom.set(xlim=(60, 330), ylim=(b1 - 90, None), title="P1, closer")
    zoom.annotate("", (frame + 3, p1), (frame + 3, b1), arrowprops=dict(arrowstyle="<->", color=LEVEL))
    zoom.annotate("P1 ÷ B1 × 100 − 100:\nthe response (dF/F)", (frame + 3, (p1 + b1) / 2), (215, 1000), fontsize=8,
                  arrowprops=dict(arrowstyle="->", color=LEVEL))
    zoom.text(87, b1 - 12, "B1 (mean of\nits window)", ha="center", va="top", fontsize=8)
    first = result.fits["Tau"][0]
    zoom.annotate("fit starts 4 frames\nafter the maximum", (first, trace[first]), (first + 40, p1 - 40),
                  fontsize=8, arrowprops=dict(arrowstyle="->", color=FIT))
    save(figure, "evoked_brightness.png")


# ---------------------------------------------------------------------------
# Stimulated ÷ unstimulated: the pulse-train protocol
# ---------------------------------------------------------------------------


def ratio_figure(data):
    protocol = pulse_train()
    recording = protocol.recordings[0]
    stimulated, unstimulated = roi_traces(data / "11P_at_200uA", "hi1.tif", "no2.tif")
    trace = make_trace(protocol, stimulated, unstimulated, recording)
    result = measure(protocol, trace, recording)

    figure, (raw, ratio) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, height_ratios=[1, 1.6], layout="constrained")
    raw.plot(stimulated, color=TRACE, lw=1, label="hi1.tif (stimulated)")
    raw.plot(unstimulated, color="0.55", lw=1, label="no2.tif (unstimulated, recorded right after)")
    raw.set(ylabel="ROI brightness (counts)", title="Both recordings bleach; dividing one by the other removes it")
    raw.legend(frameon=False, fontsize=8)

    ratio.plot(trace, color=TRACE, lw=1)
    shade(ratio, protocol.baselines["BL"], BASELINE, high=0.45)
    shade(ratio, recording.baselines["BLPre11"], BASELINE, high=0.45)
    for pulse in protocol.pulses:
        stimulus, window = protocol.pulse_timing(pulse, recording)
        shade(ratio, window, PEAK, low=0.55)
    mark(ratio, result, protocol, labels=False)
    for name in ("P1", "P2", "P10", "P11"):
        frame, value = result.peaks[name]
        ratio.annotate(name, (frame, value), (3, 4), textcoords="offset points", fontsize=8)
    bl = result.values["BL"]
    frame, p1 = result.peaks["P1"]
    ratio.annotate("", (frame - 4, p1), (frame - 4, bl), arrowprops=dict(arrowstyle="<->", color=LEVEL))
    ratio.text(frame - 8, (p1 + bl) / 2, "P1 − BL", ha="right", fontsize=8)
    pre = result.values["BLPre11"]
    frame, p11 = result.peaks["P11"]
    ratio.annotate("", (frame + 4, p11), (frame + 4, pre), arrowprops=dict(arrowstyle="<->", color=LEVEL))
    ratio.text(frame + 8, (p11 + pre) / 2, "P11 − BLPre11\n(its windows are set for each recording)", fontsize=8, va="center")
    ratio.text(0.98, 0.95, f"P2/P1 = {result.values['P2/P1']:.0f} %\nP10/P1 = {result.values['P10/P1']:.0f} %\n"
                           f"P11/P1 = {result.values['P11/P1']:.0f} %",
               transform=ratio.transAxes, ha="right", va="top", fontsize=8.5, bbox=dict(fc="white", ec="0.8"))
    ratio.set(xlim=(0, 700), xlabel="Frame", ylabel="hi1 ÷ no2 − 1 (%)", title="hi1.tif ÷ no2.tif with the 11P pulse-train protocol")
    save(figure, "evoked_ratio.png")


# ---------------------------------------------------------------------------
# Kinetics and spatial measures
# ---------------------------------------------------------------------------


def kinetics_figure(data):
    protocol = replace(paired_pulse(), kinetic_measures=list(KINETIC_KEYS))
    *_, trace, _, _ = paired_sample(data, protocol)
    pulse = protocol.pulse("P1")
    baseline = trace[81:93].mean()
    found = kinetics(protocol, trace, baseline, Window(81, 93), pulse.stimulus, pulse.peak)

    raw = response_trace(protocol, trace, baseline)
    smooth = smoothed(protocol, raw)
    window, stimulus = pulse.peak, pulse.stimulus
    first, last = min(stimulus, window.start), window.end - 1
    peak = window.start + int(np.argmax(smooth[window.start : window.end]))
    height = smooth[peak]
    t10, t20, t80, t90, up = (crossing(smooth, f * height, peak, first, -1) for f in (0.1, 0.2, 0.8, 0.9, 0.5))
    down = crossing(smooth, 0.5 * height, peak, last, +1)
    one_e = crossing(smooth, np.exp(-1) * height, peak, last, +1)

    figure, axes = plt.subplots(figsize=(9.5, 4.6), layout="constrained")
    frames = np.arange(len(raw))
    axes.fill_between(frames[first : last + 1], 0, raw[first : last + 1], color=PEAK, alpha=0.25, lw=0)
    axes.plot(raw, color="0.7", lw=0.8, label="response of P1")
    axes.plot(smooth, color=TRACE, lw=1.4, label="smoothed over 3 frames")
    axes.axvline(stimulus, color=STIMULUS, ls="--", lw=1)
    axes.plot(peak, height, "o", color=LEVEL)
    for level, text in ((0.1, "10 %"), (0.2, "20 %"), (np.exp(-1), "37 %"), (0.5, "50 %"), (0.8, "80 %"), (0.9, "90 %")):
        axes.axhline(level * height, color="0.6", lw=0.6, ls=":")
        axes.text(first - 2, level * height, text, ha="right", va="center", fontsize=7, color="0.4")

    def span(start, end, y, text, color=LEVEL, left=False):
        axes.annotate("", (start, y), (end, y), arrowprops=dict(arrowstyle="<->", color=color, lw=1.2))
        if left:
            axes.text(start - 1, y, text, ha="right", va="center", fontsize=8, color=color)
        else:
            axes.text((start + end) / 2, y, text, ha="center", va="bottom", fontsize=8, color=color)

    span(stimulus, peak, 1.06 * height, f"time to peak {found['time to peak']:.0f} ms", STIMULUS)
    span(stimulus, t20, 0.2 * height, f"onset {found['onset']:.0f} ms", STIMULUS, left=True)
    span(t10, t90, 0.9 * height, f"rise 10–90  {found['rise 10-90']:.0f} ms", left=True)
    span(t20, t80, 0.8 * height, f"rise 20–80  {found['rise 20-80']:.0f} ms", left=True)
    span(up, down, 0.5 * height, f"half-width {found['half-width']:.0f} ms")
    span(peak, down, 0.58 * height, f"half-decay {found['half-decay']:.0f} ms")
    span(peak, one_e, np.exp(-1) * height, f"1/e decay {found['1/e decay']:.0f} ms")
    axes.text(150, 0.03 * height, f"area, from the stimulus to the end of the peak window: {found['area']:.1f} %·s",
              fontsize=8, color="#9c5a1a", ha="center", va="bottom")
    axes.text(0.99, 0.97, f"max rise slope {found['max rise slope']:.0f} %/s\nmax decay slope {found['max decay slope']:.0f} %/s\n"
                          f"signal-to-noise {found['signal-to-noise']:.0f}",
              transform=axes.transAxes, ha="right", va="top", fontsize=8, bbox=dict(fc="white", ec="0.8"))
    axes.set(xlim=(first - 14, last + 3), ylim=(-0.08 * height, 1.18 * height), xlabel="Frame",
             ylabel="Response, P1 ÷ B1 × 100 − 100 (%)", title="Kinetic measures of P1 (300uA.tif)")
    axes.legend(frameon=False, loc="center right", fontsize=8)
    save(figure, "evoked_kinetics.png")


def spatial_figure(data):
    protocol = replace(paired_pulse(), spatial_measures=list(SPATIAL_KEYS), spatial_pulses=["P1"], near_to_far=["PPR"])
    center, electrode, trace, movie, _ = paired_sample(data, protocol)
    result = measure_spatial(protocol, movie, center, electrode, measure(protocol, trace))
    s, values = protocol.spatial, result.values

    figure, (maps, profile, latency) = plt.subplots(1, 3, figsize=(15, 4.4), width_ratios=[1, 1.25, 1], layout="constrained")
    picture = maps.imshow(result.maps["P1"], cmap="inferno", vmin=0, vmax=np.percentile(result.maps["P1"], 99.9))
    figure.colorbar(picture, ax=maps, fraction=0.046, label="Response (%)")
    for axes in (maps, latency):
        axes.contour(electrode, [0.5], colors="cyan", linewidths=1)
        for radius, color, style in ((s.near_to_um, "#4cc9f0", "--"), (s.far_from_um, "#f72585", ":"),
                                     (s.far_to_um, "#f72585", ":"), (s.region_um, "#ffd166", "-.")):
            axes.add_patch(Circle(center, radius / s.pixel_um, fill=False, edgecolor=color, linestyle=style, lw=1.2))
        axes.plot(*center, "+", color="white", ms=12, mew=1.5)
        axes.set(xticks=[], yticks=[])
    maps.plot(*result.centroids["P1"], "x", color="#06d6a0", ms=9, mew=2)
    maps.set_title("Response map of P1, with the near band (blue),\nfar band (pink), region (yellow) and centroid (green)", fontsize=9)

    radii = result.radii_um
    profile.axvspan(s.near_from_um, s.near_to_um, color="#4cc9f0", alpha=0.15, label="near band")
    profile.axvspan(s.far_from_um, s.far_to_um, color="#f72585", alpha=0.12, label="far band")
    profile.plot(radii, result.profiles["P1"], "o", color=TRACE, ms=3, label="ring averages (electrode left out)")
    a, width, c = result.fits["P1"]
    r = np.linspace(0, radii[-1], 300)
    profile.plot(r, lorentzian(r, a, width, c), color="#7b2cbf", lw=1.8, label=f"a/(1 + (r/λ)²) + c, λ = {width:.0f} µm")
    for key, color, height in (("footprint half-width", "black", 0.97), ("r50", "#e76f51", 0.88)):
        profile.axvline(values[f"P1 {key}"], color=color, ls="--", lw=1)
        profile.text(values[f"P1 {key}"], height, f" {key} {values[f'P1 {key}']:.0f} µm", transform=profile.get_xaxis_transform(), fontsize=8, va="top", color=color)
    profile.axvline(s.tail_from_um, color="0.5", ls=":", lw=1)
    profile.text(s.tail_from_um, 0.06, f" tail beyond {s.tail_from_um:.0f} µm:\n {values['P1 tail fraction']:.0%} of the signal", transform=profile.get_xaxis_transform(), fontsize=8, color="0.3")
    profile.set(xlabel="Distance from the ROI centre (µm)", ylabel="Response (%)", title="Ring averages of the map of P1")
    profile.legend(fontsize=7.5, frameon=False, loc="upper right", bbox_to_anchor=(1, 0.8))

    finite = result.latencies["P1"][np.isfinite(result.latencies["P1"])]
    picture = latency.imshow(result.latencies["P1"], cmap="viridis", vmin=np.percentile(finite, 1), vmax=np.percentile(finite, 99))
    figure.colorbar(picture, ax=latency, fraction=0.046, label="Half-rise latency after the stimulus (ms)")
    latency.set_title(f"Half-rise latency: {values['P1 latency slope']:.1f} ms later per mm,\nfar band {values['P1 far-near delay']:.1f} ms after the near band", fontsize=9)
    save(figure, "evoked_spatial.png")
    print("  centroid offset", round(values["P1 centroid offset"]), "µm; elongation", round(values["P1 elongation"], 2),
          "; heterogeneity", round(values["P1 heterogeneity"], 2), "; hot spots", round(values["P1 hot spots"], 1),
          "/mm²; PPR near-to-far", round(values["PPR near-to-far"], 2))


def decay_figure(data):
    from scipy import ndimage, stats

    from ema.evoked.spatial import response_movie

    protocol = replace(paired_pulse(), spatial_measures=list(SPATIAL_KEYS), spatial_pulses=["P1"])
    center, electrode, trace, movie, _ = paired_sample(data, protocol)
    measurement = measure(protocol, trace)
    result = measure_spatial(protocol, movie, center, electrode, measurement)
    decay, values, s = result.decays["P1"], result.values, protocol.spatial

    figure = plt.figure(figsize=(15, 4.0), layout="constrained")
    grid = figure.add_gridspec(1, 5, width_ratios=[1, 1, 1, 1.7, 1.5])
    size = s.frames_before_peak + s.frames_from_peak
    first = measurement.peaks["P1"][0] - s.frames_before_peak
    for column, k in enumerate((0, 6, 12)):
        axes = figure.add_subplot(grid[column])
        frames = slice(first + k * size, first + (k + 1) * size)
        image = ndimage.gaussian_filter(response_movie(protocol, movie, protocol.baselines["B1"], frames).mean(axis=0), s.smoothing_px)
        axes.imshow(image / np.percentile(image, 99.9), cmap="inferno", vmin=0, vmax=1)
        axes.contour(electrode, [0.5], colors="cyan", linewidths=1)
        for radius, color, style in ((s.near_to_um, "#4cc9f0", "--"), (s.far_from_um, "#f72585", ":"), (s.far_to_um, "#f72585", ":")):
            axes.add_patch(Circle(center, radius / s.pixel_um, fill=False, edgecolor=color, linestyle=style, lw=1.2))
        axes.set(xticks=[], yticks=[], title=f"{decay.times_ms[k]:.0f} ms after the peak\n(scaled to its own maximum)")

    axes = figure.add_subplot(grid[3])
    for curve, color, label in ((decay.near, "#4cc9f0", "near band (0–160 µm)"), (decay.far, "#f72585", "far band (400–640 µm)")):
        t_half = half_time(decay.times_ms, curve)
        axes.plot(decay.times_ms, curve / curve[0], color=color, lw=1.6, label=f"{label}: half at {t_half:.0f} ms")
        axes.plot([t_half, t_half], [0, 0.5], color=color, ls=":", lw=1.2)
    axes.axhline(0.5, color="0.6", ls="--", lw=0.8)
    axes.text(0.97, 0.55, f"far-near decay ratio\n{values['P1 far-near decay ratio']:.2f}", transform=axes.transAxes,
              ha="right", va="top", fontsize=8.5, bbox=dict(fc="white", ec="0.8"))
    axes.set(xlim=(0, 800), ylim=(-0.05, 1.1), xlabel="Time after the peak (ms)", ylabel="Share of the value at the peak",
             title="Near and far band of P1 (300uA.tif)")
    axes.legend(frameon=False, fontsize=8, loc="upper right")

    axes = figure.add_subplot(grid[4])
    distance = np.arange(len(decay.half_decay_ms)) * s.pixel_um
    ok = np.isfinite(decay.half_decay_ms)
    axes.axvspan(s.near_from_um, s.near_to_um, color="#4cc9f0", alpha=0.15)
    axes.axvspan(s.far_from_um, s.far_to_um, color="#f72585", alpha=0.12)
    axes.plot(distance[ok], decay.half_decay_ms[ok], "o", color=TRACE, ms=3.5, label="half-decay time of each ring")
    slope, intercept, *_ = stats.theilslopes(decay.half_decay_ms[ok], distance[ok] / 1000)
    axes.plot(distance, intercept + slope * distance / 1000, color="#7b2cbf", lw=1.6,
              label=f"Theil–Sen slope {values['P1 decay-distance slope']:.0f} ms/mm")
    axes.set(xlabel="Distance of the ring (k × 16 µm)", ylabel="Half-decay time after the peak (ms)",
             title="Decay-distance slope")
    axes.legend(frameon=False, fontsize=8, loc="lower left")
    save(figure, "evoked_decay.png")


def main():
    data = Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE_DATA
    FIGURES.mkdir(exist_ok=True)
    brightness_figure(data)
    ratio_figure(data)
    kinetics_figure(data)
    spatial_figure(data)
    decay_figure(data)


if __name__ == "__main__":
    main()
