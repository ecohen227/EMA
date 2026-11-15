"""Fast redrawing of a few moving things on a matplotlib canvas."""


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
            if artist.axes is not None:
                self.canvas.figure.draw_artist(artist)

    def update(self):
        if self.background is None:
            self.canvas.draw_idle()
            return
        self.canvas.restore_region(self.background)
        self._draw_artists()
        self.canvas.blit(self.canvas.figure.bbox)
