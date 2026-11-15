"""The two plots of the ROI Selection window: the image with its ROI and electrode, and the ROI trace."""

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.patches import Circle, PathPatch
from matplotlib.path import Path as Outline
from PyQt5.QtCore import pyqtSignal

from .selections import mask_runs

ROI_COLOR = "white"
ELECTRODE_COLOR = "cyan"
LEFT_BUTTON, RIGHT_BUTTON = 1, 3
MOVE_ROI, EDIT_ELECTRODE = "move the ROI", "edit the electrode"


class Blitter:
    """Redraws a few moving things over a saved picture of the rest of the figure.

    Redrawing a whole figure takes about 50 ms, too slow to follow the mouse.
    The artists listed here are left out of the normal drawing and painted on
    top by `update`, which takes a few milliseconds. They should be simple
    shapes: an image would be as slow to paint as the whole figure.
    """

    def __init__(self, canvas):
        self.canvas = canvas
        self.artists = []
        self.background = None
        canvas.mpl_connect("draw_event", self._after_full_draw)

    def set_artists(self, *artists):
        for artist in artists:
            artist.set_animated(True)
        self.artists = artists

    def _after_full_draw(self, event):
        self.background = self.canvas.copy_from_bbox(self.canvas.figure.bbox)
        self._draw_artists()

    def _draw_artists(self):
        for artist in self.artists:
            self.canvas.figure.draw_artist(artist)

    def update(self):
        if self.background is None:
            self.canvas.draw_idle()
            return
        self.canvas.restore_region(self.background)
        self._draw_artists()
        self.canvas.blit(self.canvas.figure.bbox)


class ImageView(FigureCanvasQTAgg):
    """An image with a draggable ROI circle and an electrode mask that can be redrawn.

    With the MOVE_ROI tool, clicking or dragging moves the ROI. With the
    EDIT_ELECTRODE tool, dragging draws an outline: the left mouse button adds
    the outlined area to the mask, the right button removes it. With the tool
    set to None the image is only looked at.
    """

    roi_moved = pyqtSignal(int, int)  # new centre, while dragging
    roi_dropped = pyqtSignal()
    electrode_outlined = pyqtSignal(object, bool)  # outlined area (mask), True to add / False to remove

    def __init__(self, figsize=(5, 4.4)):
        super().__init__(Figure(figsize=figsize, layout="constrained"))
        self.tool = MOVE_ROI
        self.axes = self.figure.add_subplot()
        self.axes.axis("off")
        self.image = None
        self.colorbar = None
        self.electrode = PathPatch(
            Outline(np.empty((0, 2))), facecolor=to_rgba(ELECTRODE_COLOR, 0.45), edgecolor="none", antialiased=False
        )
        self.roi = Circle((0, 0), 1, fill=False, edgecolor=ROI_COLOR, linewidth=2, visible=False)
        self.axes.add_patch(self.electrode)
        self.axes.add_patch(self.roi)
        (self.outline,) = self.axes.plot([], [], color=ELECTRODE_COLOR, linewidth=1.5)
        self.blitter = Blitter(self)
        self.blitter.set_artists(self.electrode, self.roi, self.outline)

        self._grab_offset = None  # ROI centre minus mouse position while the ROI is dragged
        self._outline_points = []
        self._outline_adds = True
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)

    # ------------------------------------------------------------------
    # What is shown
    # ------------------------------------------------------------------

    def show_image(self, data, label, colormap="inferno", limits=None):
        """Show a 2D array. `limits` is (darkest, brightest); by default the 1st and 99.9th percentile."""
        low, high = limits or np.percentile(data, [1, 99.9])
        if self.image is None or self.image.get_array().shape != data.shape:
            self._start_image(data)
        self.image.set_data(data)
        self.image.set_cmap(colormap)
        self.image.set_clim(low, max(high, low + 1e-9))
        self.colorbar.set_label(label)
        self.draw_idle()

    def _start_image(self, data):
        if self.image is not None:
            self.colorbar.remove()
            self.image.remove()
        self.image = self.axes.imshow(data, interpolation="nearest")
        self.colorbar = self.figure.colorbar(self.image, ax=self.axes, fraction=0.046, pad=0.03)

    def show_roi(self, center, radius):
        self.roi.set(center=center, radius=radius, visible=True)
        self.blitter.update()

    def show_electrode(self, mask):
        # One rectangle per run of masked pixels in a row; pixel (x, y) covers x - 0.5 to x + 0.5.
        rectangles = [
            Outline([(first - 0.5, row - 0.5), (last + 0.5, row - 0.5), (last + 0.5, row + 0.5), (first - 0.5, row + 0.5), (0, 0)], closed=True)
            for row, first, last in mask_runs(mask)
        ]
        self.electrode.set_path(Outline.make_compound_path(*rectangles) if rectangles else Outline(np.empty((0, 2))))
        self.blitter.update()

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    def _position(self, event):
        """Mouse position in image pixels, or None outside the image."""
        if self.image is None or event.inaxes is not self.axes or event.xdata is None:
            return None
        return event.xdata, event.ydata

    def _on_press(self, event):
        position = self._position(event)
        if position is None:
            return
        if self.tool == MOVE_ROI and event.button == LEFT_BUTTON:
            # Grabbing inside the circle drags it without a jump; clicking elsewhere centres it there.
            inside = self.roi.contains_point(self.axes.transData.transform(position))
            self._grab_offset = np.subtract(self.roi.center, position) if inside else np.zeros(2)
            self._move_roi(position)
        elif self.tool == EDIT_ELECTRODE and event.button in (LEFT_BUTTON, RIGHT_BUTTON):
            self._outline_points = [position]
            self._outline_adds = event.button == LEFT_BUTTON
            self.outline.set_linestyle("-" if self._outline_adds else "--")

    def _on_motion(self, event):
        position = self._position(event)
        if position is None:
            return
        if self._grab_offset is not None:
            self._move_roi(position)
        elif self._outline_points:
            self._outline_points.append(position)
            self.outline.set_data(*zip(*self._outline_points))
            self.blitter.update()

    def _on_release(self, event):
        if self._grab_offset is not None:
            self._grab_offset = None
            self.roi_dropped.emit()
        elif self._outline_points:
            points, self._outline_points = self._outline_points, []
            self.outline.set_data([], [])
            self.blitter.update()
            if len(points) >= 3:
                self.electrode_outlined.emit(self._area_inside(points), self._outline_adds)

    def _move_roi(self, position):
        """Move the ROI to the mouse, on whole pixels and never outside the image."""
        rows, columns = self.image.get_array().shape
        x, y = np.round(position + self._grab_offset).astype(int)
        center = int(np.clip(x, 0, columns - 1)), int(np.clip(y, 0, rows - 1))
        if center != tuple(self.roi.center):
            self.roi_moved.emit(*center)

    def _area_inside(self, points):
        """Mask of the pixels whose centre lies inside a hand-drawn outline."""
        rows, columns = self.image.get_array().shape
        y, x = np.mgrid[:rows, :columns]
        pixels = np.column_stack([x.ravel(), y.ravel()])
        return Outline(points).contains_points(pixels).reshape(rows, columns)


class TraceView(FigureCanvasQTAgg):
    """dF/F of the ROI over time, with the baseline and search windows shaded."""

    def __init__(self, figsize=(6, 4.4)):
        super().__init__(Figure(figsize=figsize, layout="constrained"))
        self.axes = self.figure.add_subplot()
        self.line = None
        self.frame_marker = None
        self.blitter = Blitter(self)

    def show_trace(self, trace, settings, title="", peak=None):
        """Draw a trace with the windows of the settings. `peak` is the peak frame, if it is known."""
        self.axes.clear()
        # The curve is drawn before the shaded windows: drawn after them, matplotlib keeps the old height of the plot.
        (self.line,) = self.axes.plot(trace, color="#1f4e79", linewidth=1.2)
        self.axes.axvspan(*settings.baseline_frames, color="0.85", label="Baseline window")
        self.axes.axvspan(*settings.search_frames, color="#fde9c9", label="Response search window")
        if peak is not None:
            first, last = peak - settings.peak_frames_before, peak + settings.peak_frames_after
            self.axes.axvspan(first, last, color="#2a9d8f", label="Frames averaged at the peak")
        self.frame_marker = self.axes.axvline(0, color="red", linestyle="--", linewidth=1, visible=False)
        self.axes.set(xlabel="Frame", ylabel="dF/F in the ROI (%)", title=title)
        self.axes.set_xlim(0, len(trace))
        self.axes.legend(loc="upper right", fontsize="small", frameon=False)
        self.blitter.set_artists(self.line, self.frame_marker)
        self.draw_idle()

    def update_trace(self, trace):
        """Replace the curve without rescaling the axes. Fast enough to follow the ROI while it is dragged."""
        self.line.set_ydata(trace)
        self.blitter.update()

    def show_frame(self, frame):
        """Mark a frame with a vertical line, or hide the line with None."""
        if self.frame_marker is None:
            return
        self.frame_marker.set_visible(frame is not None)
        if frame is not None:
            self.frame_marker.set_xdata([frame, frame])
        self.blitter.update()

    def clear(self):
        self.axes.clear()
        self.line = self.frame_marker = None
        self.blitter.set_artists()
        self.draw_idle()
