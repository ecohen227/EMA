"""The example trace with the protocol's windows drawn on it. Windows, fits and stimuli can be dragged.

Baseline windows are grey bands in the bottom third of the plot, exponential
fits purple bands in the middle third (with the fitted curve), peak windows
orange bands in the top third, and stimuli red dashed lines. Dragging the
edge of a band moves that edge, dragging inside a band moves the whole band,
and dragging a red line moves the stimulus.
"""

from dataclasses import dataclass

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PyQt5.QtCore import Qt, pyqtSignal

from ..blit import Blitter
from ..evoked.protocol import Window

BASELINE_BAND = (0.0, 0.3)  # bottom and top of the bands, as fractions of the plot height
FIT_BAND = (0.35, 0.65)
PEAK_BAND = (0.7, 1.0)
BANDS = {"baseline": BASELINE_BAND, "fit": FIT_BAND, "peak": PEAK_BAND}
GRAB_PIXELS = 6
MIN_FIT_FRAMES = 3
TRACE_COLOR, BASELINE_COLOR, PEAK_COLOR = "#1f4e79", "#8d99ae", "#f4a261"
STIMULUS_COLOR, LEVEL_COLOR, FIT_COLOR = "#d62828", "#2b2d42", "#7b2cbf"


@dataclass
class Handle:
    """Something on the plot that can be dragged: a baseline window, a peak window, a fit or a stimulus."""

    kind: str  # "baseline", "peak", "fit" or "stimulus"
    name: str  # the baseline's, pulse's or fit's name
    start: int
    end: int
    origin: int = 0  # for a fit: the frame its start is counted from (the maximum it follows, or 0)


class TracePlot(FigureCanvasQTAgg):
    dragged = pyqtSignal()  # the protocol was changed by dragging
    drag_finished = pyqtSignal()

    def __init__(self):
        super().__init__(Figure(figsize=(7, 3.6), layout="constrained"))
        self.axes = self.figure.add_subplot()
        self.dt = 4.849
        self.axes.secondary_xaxis("top", functions=(lambda f: f * self.dt, lambda ms: ms / self.dt)).set_xlabel("Time (ms)")
        self.blitter = Blitter(self)
        self.toolbar = None  # set by the window; dragging is off while it zooms or pans
        self.protocol = self.recording = None
        self.title = None  # (label, trace kind) of what is on show
        self.handles = []
        self.overlays = []
        self._drag = None  # (handle, part, frame where it was grabbed)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def show_trace(self, protocol, trace, recording, measurement, title="", keep_view=False):
        """Draw the trace and everything on it. The axes fit the trace, or stay as they are with `keep_view`."""
        limits = (self.axes.get_xlim(), self.axes.get_ylim())
        self.protocol, self.recording, self.dt = protocol, recording, protocol.sampling_interval_ms
        self.title = (title, protocol.trace)
        for artist in self.overlays:
            artist.remove()
        self.overlays = []
        self.axes.clear()
        self.axes.plot(trace, color=TRACE_COLOR, linewidth=1)
        self.axes.set_xlim(0, len(trace))
        self.axes.set(xlabel="Frame", ylabel=f"Trace ({protocol.trace_unit})", title=title)
        if keep_view:
            self.axes.set_xlim(limits[0])
            self.axes.set_ylim(limits[1])
        self.show_measurement(measurement, redraw=False)
        self.draw_idle()

    def clear(self, message=""):
        self.protocol, self.title = None, None
        for artist in self.overlays:
            artist.remove()
        self.overlays, self.handles = [], []
        self.axes.clear()
        self.axes.text(0.5, 0.5, message, ha="center", va="center", wrap=True, transform=self.axes.transAxes)
        self.draw_idle()

    def show_measurement(self, measurement, redraw=True):
        """Draw the windows, stimuli and what was measured again, without touching the trace."""
        for artist in self.overlays:
            artist.remove()
        self.overlays, self.handles = [], []
        if self.protocol is None:
            return
        band = self.axes.get_xaxis_transform()  # x in frames, y as a fraction of the plot height
        for name in self.protocol.baselines:
            window = self.protocol.baseline_window(name, self.recording)
            if window is not None:
                self._band(window, BASELINE_BAND, BASELINE_COLOR, name, band)
                self.handles.append(Handle("baseline", name, window.start, window.end))
        crowded = len(self.protocol.pulses) > 4  # labels of close pulses go on two rows
        for index, pulse in enumerate(self.protocol.pulses):
            stimulus, window = self.protocol.pulse_timing(pulse, self.recording)
            if window is not None:
                self._band(window, PEAK_BAND, PEAK_COLOR, pulse.name, band, lower=crowded and index % 2)
                self.handles.append(Handle("peak", pulse.name, window.start, window.end))
            if stimulus is not None:
                self._add(Line2D([stimulus, stimulus], [0, 1], transform=band, color=STIMULUS_COLOR, linestyle="--", linewidth=1))
                self.handles.append(Handle("stimulus", pulse.name, stimulus, stimulus))

        for fit in self.protocol.fits:
            frames = measurement.fit_frames.get(fit.name)
            if frames is None:
                continue
            first, last = frames
            self._band(Window(first, last), FIT_BAND, FIT_COLOR, self._fit_label(fit, measurement), band)
            self.handles.append(Handle("fit", fit.name, first, last, first - fit.start))
        for window, level in measurement.levels.values():
            self._add(Line2D([window.start, window.end], [level, level], color=LEVEL_COLOR, linewidth=2.5))
        for frame, value in measurement.peaks.values():
            self._add(Line2D([frame], [value], color=LEVEL_COLOR, marker="o", markersize=5, linestyle=""))
        for curve in measurement.fits.values():
            if curve is not None:
                first, values = curve
                self._add(Line2D(first + np.arange(len(values)), values, color=FIT_COLOR, linewidth=2.2, alpha=0.9))
        self.blitter.set_artists(*self.overlays)
        if redraw:
            self.blitter.update()

    def _band(self, window, band, color, label, transform, lower=False):
        bottom, top = band
        alpha = 0.18 if band is FIT_BAND else 0.3
        self._add(Rectangle((window.start, bottom), window.end - window.start, top - bottom, transform=transform,
                            facecolor=color, alpha=alpha, edgecolor=color, linewidth=1))
        if band is PEAK_BAND:
            x, y, ha, va = (window.start + window.end) / 2, top - (0.08 if lower else 0.02), "center", "top"
        elif band is FIT_BAND:
            x, y, ha, va = window.start, (bottom + top) / 2, "left", "center"
        else:
            x, y, ha, va = (window.start + window.end) / 2, bottom + 0.02, "center", "bottom"
        color = FIT_COLOR if band is FIT_BAND else "black"
        self._add(self.axes.text(x, y, label, transform=transform, ha=ha, va=va, fontsize=8, color=color))

    @staticmethod
    def _fit_label(fit, measurement):
        values = [measurement.values.get(name, np.nan) for name in fit.measure_names()]
        if not np.isfinite(values[0]):
            return f" {fit.name}: did not converge"
        if len(values) == 1:
            return f" {fit.name}: τ = {values[0]:.0f} ms"
        return f" {fit.name}: τ fast {values[0]:.0f} ms, slow {values[1]:.0f} ms"

    def _add(self, artist):
        if not artist.axes:
            self.axes.add_artist(artist)
        self.overlays.append(artist)

    # ------------------------------------------------------------------
    # Dragging
    # ------------------------------------------------------------------

    def _grab(self, event):
        """What is under the mouse: (handle, part), part being "start", "end" or "move". None if nothing."""
        if self.protocol is None or event.inaxes is not self.axes or (self.toolbar and self.toolbar.mode):
            return None
        height = self.axes.transAxes.inverted().transform((event.x, event.y))[1]
        pixel = lambda frame: self.axes.transData.transform((frame, 0))[0]  # noqa: E731
        in_band = [h for h in self.handles if h.kind != "stimulus" and _inside(height, BANDS[h.kind])]
        near = [(abs(pixel(frame) - event.x), handle, part)
                for handle in in_band for part, frame in (("start", handle.start), ("end", handle.end))]
        near += [(abs(pixel(h.start) - event.x), h, "move") for h in self.handles if h.kind == "stimulus"]
        near = [item for item in near if item[0] <= GRAB_PIXELS]
        if near:  # the edge or stimulus line closest to the mouse
            _, handle, part = min(near, key=lambda item: item[0])
            return handle, part
        for handle in in_band:
            if handle.start <= event.xdata <= handle.end:
                return handle, "move"
        return None

    def _on_press(self, event):
        grabbed = self._grab(event)
        if grabbed and event.button == 1:
            self._drag = (*grabbed, round(event.xdata))

    def _on_motion(self, event):
        if self._drag is None:
            grabbed = self._grab(event)
            shape = Qt.ArrowCursor
            if grabbed:
                shape = Qt.SizeAllCursor if grabbed[1] == "move" and grabbed[0].kind != "stimulus" else Qt.SizeHorCursor
            self.setCursor(shape)
            return
        if event.xdata is None:
            return
        handle, part, grabbed_at = self._drag
        shift = round(event.xdata) - grabbed_at
        start, end = handle.start, handle.end
        if part == "start":
            start = min(start + shift, end - 1)
        elif part == "end":
            end = max(end + shift, start + 1)
        else:
            shift = max(shift, -start)  # never before frame 0
            start, end = start + shift, end + shift
        start = max(start, handle.origin if handle.kind == "fit" else 0)
        if handle.kind == "fit" and end - start < MIN_FIT_FRAMES:
            return
        self._apply(handle, start, end)
        self.dragged.emit()

    def _apply(self, handle, start, end):
        if handle.kind == "fit":
            fit = next(f for f in self.protocol.fits if f.name == handle.name)
            fit.start, fit.length = start - handle.origin, end - start
        elif handle.kind == "baseline":
            self.protocol.set_baseline_window(handle.name, Window(start, end), self.recording)
        elif handle.kind == "peak":
            self.protocol.set_pulse_timing(self.protocol.pulse(handle.name), self.recording, peak=Window(start, end))
        else:
            self.protocol.set_pulse_timing(self.protocol.pulse(handle.name), self.recording, stimulus=start)

    def _on_release(self, event):
        if self._drag is not None:
            self._drag = None
            self.drag_finished.emit()


def _inside(value, band):
    return band[0] <= value <= band[1]
