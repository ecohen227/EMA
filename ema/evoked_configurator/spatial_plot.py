"""The spatial preview: a pulse's response map with its rings, and its ring profile with the footprint fit,
or how it decays near and far from the centre."""

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..evoked.spatial import half_time, lorentzian

RESPONSE, LATENCY, DECAY = "Response map", "Half-rise latency", "Decay with distance"
NEAR_COLOR, FAR_COLOR, REGION_COLOR, CENTROID_COLOR = "#4cc9f0", "#f72585", "#ffd166", "#06d6a0"


class SpatialView(QWidget):
    pulse_chosen = pyqtSignal()  # a pulse or a view was chosen: the maps must be measured again

    def __init__(self):
        super().__init__()
        self.pulse_box = QComboBox()
        self.pulse_box.setMinimumWidth(90)
        self.pulse_box.currentIndexChanged.connect(self.pulse_chosen)
        self.view_box = QComboBox()
        self.view_box.addItems([RESPONSE, LATENCY, DECAY])
        self.view_box.setToolTip("The half-rise latency is computed when a release-spread measure is chosen.")
        self.view_box.currentIndexChanged.connect(self.pulse_chosen)
        self.canvas = FigureCanvasQTAgg(Figure(figsize=(7, 3.6), layout="constrained"))
        # The colour bar has an area of its own that is redrawn in place: a colour bar that is removed and made
        # again confuses matplotlib's layout once its image has been cleared.
        self.map_axes, self.colorbar_axes, self.profile_axes = self.canvas.figure.subplots(1, 3, width_ratios=[1, 0.05, 1.25])
        self.message = QLabel()
        self.message.setStyleSheet("color: gray")
        top = QHBoxLayout()
        top.addWidget(QLabel("Pulse:"))
        top.addWidget(self.pulse_box)
        top.addWidget(QLabel("Show:"))
        top.addWidget(self.view_box)
        top.addWidget(self.message, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.canvas, 1)
        self.state = None

    @property
    def pulse(self):
        return self.pulse_box.currentText() or None

    @property
    def wants_decay(self):
        return self.view_box.currentText() == DECAY

    def show_pulses(self, names, keep=None):
        current = keep or self.pulse
        self.pulse_box.blockSignals(True)
        self.pulse_box.clear()
        self.pulse_box.addItems(names)
        if current in names:
            self.pulse_box.setCurrentIndex(names.index(current))
        self.pulse_box.blockSignals(False)

    def show_result(self, protocol, result, center, electrode):
        self.state = (protocol, result, center, electrode)
        self.redraw()

    def clear(self, message):
        self.state = None
        self.message.setText(message)
        for axes in (self.map_axes, self.colorbar_axes, self.profile_axes):
            axes.clear()
            axes.set_axis_off()
        self.canvas.draw_idle()

    def redraw(self):
        if self.state is None:
            return
        protocol, result, center, electrode = self.state
        name = self.pulse
        s = protocol.spatial
        for axes in (self.map_axes, self.colorbar_axes, self.profile_axes):
            axes.clear()
            axes.set_axis_on()
        if name not in result.maps:
            self.clear(f"{name} could not be measured on this recording." if name else "")
            return
        self.message.setText("")

        latency = self.view_box.currentText() == LATENCY
        if latency and name not in result.latencies:
            self.message.setText("Choose a release-spread measure to see the latency.")
            latency = False
        image = result.latencies[name] if latency else result.maps[name]
        finite = image[np.isfinite(image)]
        low, high = (np.percentile(finite, [1, 99]) if latency else (0, np.percentile(finite, 99.9))) if finite.size else (0, 1)
        picture = self.map_axes.imshow(image, cmap="viridis" if latency else "inferno", vmin=low, vmax=max(high, low + 1e-9))
        self.canvas.figure.colorbar(picture, cax=self.colorbar_axes, label="ms after the stimulus" if latency else "%")
        if electrode is not None and electrode.any():
            self.map_axes.contour(electrode, [0.5], colors="cyan", linewidths=1)
        px = s.pixel_um
        for radius, color, style in ((s.near_to_um, NEAR_COLOR, "--"), (s.far_from_um, FAR_COLOR, ":"),
                                     (s.far_to_um, FAR_COLOR, ":"), (s.region_um, REGION_COLOR, "-.")):
            self.map_axes.add_patch(Circle(center, radius / px, fill=False, edgecolor=color, linestyle=style, linewidth=1.2))
        self.map_axes.plot(*center, "+", color="white", markersize=12, markeredgewidth=1.5)
        centroid = result.centroids.get(name)
        if centroid is not None:
            self.map_axes.plot(*centroid, "x", color=CENTROID_COLOR, markersize=9, markeredgewidth=2)
        self.map_axes.set(xticks=[], yticks=[], title=f"{name}: {'latency' if latency else 'response'} map")

        if self.wants_decay and name in result.decays:
            self.draw_decay(result.decays[name], result.values, name)
            self.canvas.draw_idle()
            return
        radii = result.radii_um
        profile = result.profiles[name]
        axes = self.profile_axes
        axes.axvspan(s.near_from_um, s.near_to_um, color=NEAR_COLOR, alpha=0.15, label="near band")
        axes.axvspan(s.far_from_um, s.far_to_um, color=FAR_COLOR, alpha=0.12, label="far band")
        axes.plot(radii, profile, "o", color="#1f4e79", markersize=3, label="ring averages")
        fit = result.fits.get(name)
        if fit is not None:
            r = np.linspace(0, radii[-1], 300)
            axes.plot(r, lorentzian(r, *fit), color="#7b2cbf", linewidth=1.8, label=f"fit, width λ = {fit[1]:.0f} µm")
        for key, color, text, height in (("footprint half-width", "black", "half-width", 0.98), ("r50", "#e76f51", "r50", 0.9)):
            value = result.values.get(f"{name} {key}", np.nan)
            if np.isfinite(value):
                axes.axvline(value, color=color, linestyle="--", linewidth=1)
                axes.text(value, height, f" {text} {value:.0f} µm", transform=axes.get_xaxis_transform(), fontsize=7, va="top", color=color)
        axes.axhline(0, color="0.7", linewidth=0.8)
        axes.set(xlabel="Distance from the ROI centre (µm)", ylabel="Response (%)", title="Ring averages")
        axes.legend(fontsize=7, frameon=False, loc="upper right" if fit is None else "center right")
        self.canvas.draw_idle()

    def draw_decay(self, decay, values, name):
        """The near and the far band from the peak on, each as a share of its value at the peak."""
        axes = self.profile_axes
        times = decay.times_ms
        for curve, color, label in ((decay.near, NEAR_COLOR, "near band"), (decay.far, FAR_COLOR, "far band")):
            if np.isfinite(curve[0]) and curve[0] > 0:
                t_half = half_time(times, curve)
                text = f"{label}, half at {t_half:.0f} ms" if np.isfinite(t_half) else label
                axes.plot(times, curve / curve[0], color=color, linewidth=1.6, label=text)
                if np.isfinite(t_half):
                    axes.plot([t_half, t_half], [0, 0.5], color=color, linestyle=":", linewidth=1)
        axes.axhline(0.5, color="0.6", linestyle="--", linewidth=0.8)
        axes.axhline(0, color="0.7", linewidth=0.8)
        lines = []
        for key, unit in (("far-near decay ratio", ""), ("decay-distance slope", " ms/mm")):
            value = values.get(f"{name} {key}", np.nan)
            if np.isfinite(value):
                lines.append(f"{key}: {value:.3g}{unit}")
        if lines:
            axes.text(0.98, 0.6, "\n".join(lines), transform=axes.transAxes, ha="right", va="top", fontsize=7)
        axes.set(xlabel="Time after the peak (ms)", ylabel="Share of the value at the peak", ylim=(-0.1, 1.15),
                 title="Decay near and far from the centre")
        axes.legend(fontsize=7, frameon=False, loc="upper right")
