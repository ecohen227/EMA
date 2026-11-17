"""The settings of the spontaneous-event detector, with the standard detector's values as defaults.

Each setting carries its label, unit, section and help text (see
ema.definitions.setting). The configurator's form and the documentation's
tables are both built from this one list. Times are given in ms and distances
in µm; the detector converts them to frames and pixels with the time between
frames and the pixel size. Settings marked `advanced` are shown under Advanced
in the configurator.
"""

from dataclasses import dataclass

from ..definitions import Settings, setting
from ..recordings import FRAME_MS, PIXEL_UM

GROUPS = ("Movie", "Event shape", "Spatial filter", "Detection", "Controls", "Measuring", "Tissue", "Signal", "Echoes")


@dataclass
class DetectorSettings(Settings):
    # --- Movie ---
    frame_ms: float = setting(FRAME_MS, "Movie", "Time between frames", "The time between two frames of the recordings.",
                              "float", "ms", minimum=0.001, maximum=10000.0, step=0.001)
    pixel_um: float = setting(PIXEL_UM, "Movie", "Pixel size", "The width of one pixel in the slice (16 µm with the 4× "
                              "objective).", "float", "µm", minimum=0.01, maximum=1000.0, step=1.0)
    first_frames: int = setting(20, "Movie", "Leave out the first", "Frames left out at the start of each recording, "
                                "counted after the first frame of the file (which EMA always drops).", "int", "frames",
                                minimum=0, maximum=100000)
    last_frames: int = setting(10, "Movie", "Leave out the last", "Frames left out at the end of each recording.", "int",
                               "frames", minimum=0, maximum=100000)

    # --- Event shape: the time course the detector looks for ---
    rise_ms: float = setting(12.0, "Event shape", "Rise time constant", "How fast the events the detector looks for rise. "
                             "The shape is A·(exp(−t/decay) − exp(−t/rise)), like a dLight event.", "float", "ms",
                             minimum=0.1, maximum=10000.0, step=1.0)
    decay_ms: float = setting(200.0, "Event shape", "Decay time constant", "How fast the events the detector looks for decay.",
                              "float", "ms", minimum=0.1, maximum=10000.0, step=10.0)
    before_ms: float = setting(100.0, "Event shape", "Baseline before the onset", "How much of the trace before an onset the "
                               "shape covers.", "float", "ms", advanced=True, minimum=0.0, maximum=10000.0, step=10.0)
    after_ms: float = setting(600.0, "Event shape", "Length after the onset", "How much of the trace after an onset the shape "
                              "covers.", "float", "ms", advanced=True, minimum=10.0, maximum=10000.0, step=10.0)
    line_baseline: bool = setting(True, "Event shape", "Allow a sloping baseline", "The shape is compared together with a "
                                  "straight line, so a slow drift under an event does not change its strength.", "bool",
                                  advanced=True)

    # --- Spatial filter ---
    blur_um: float = setting(128.0, "Spatial filter", "Pooling width", "Neighbouring pixels are pooled with a Gaussian blur "
                             "of this width (its σ). About the width of a typical event finds the most events; 64 µm is "
                             "better for small ones.", "float", "µm", minimum=0.0, maximum=2000.0, step=16.0)
    remove_field: bool = setting(True, "Spatial filter", "Remove the field-wide signal", "Each filtered frame's median over "
                                 "the tissue is subtracted, which removes changes shared by the whole field.", "bool",
                                 advanced=True)

    # --- Detection ---
    event_z: float = setting(8.0, "Detection", "Event threshold", "A region whose strength reaches this many times the noise "
                             "is an event.", "float", "× noise", minimum=1.0, maximum=100.0, step=0.5)
    region_z: float = setting(3.0, "Detection", "Region threshold", "Neighbouring pixels and frames at least this many times "
                              "the noise form one region; each region is one candidate event.", "float", "× noise",
                              advanced=True, minimum=0.5, maximum=100.0, step=0.5)
    end_trim_ms: float = setting(320.0, "Detection", "Leave out onsets in the last", "Onsets this close to the end of the "
                                 "searched part are not counted: there the event shape reaches the last frames, where the "
                                 "bleaching correction is least certain.", "float", "ms", advanced=True, minimum=0.0,
                                 maximum=10000.0, step=10.0)

    # --- Controls ---
    sign_flip: bool = setting(True, "Controls", "Count sign-flipped events", "The detector also searches the movie turned "
                              "upside down (dips instead of rises). What it finds there estimates the false alarms.", "bool")
    time_reversed: bool = setting(True, "Controls", "Count time-reversed events", "The detector also searches the movie played "
                                  "backwards. Real events, with a fast rise and a slow decay, are mostly not found.", "bool")

    # --- Measuring ---
    near_um: float = setting(480.0, "Measuring", "Near the ROI centre within", "For the share of events near the ROI "
                             "centre.", "float", "µm", minimum=0.0, maximum=5000.0, step=16.0)
    site_um: float = setting(100.0, "Measuring", "Same site within", "Events closer than this are counted as the same site, "
                             "for the recurring-site measures.", "float", "µm", minimum=1.0, maximum=5000.0, step=10.0)
    together_ms: float = setting(1000.0, "Measuring", "Together within", "Two events of a recording closer in time than "
                                 "this count as together, for the share of events together.", "float", "ms",
                                 minimum=1.0, maximum=60000.0, step=100.0)
    fit_radius_um: float = setting(400.0, "Measuring", "Fit the width within", "The Gaussian that measures an event's width "
                                   "and peak is fitted to the pixels within this distance of the event.", "float", "µm",
                                   advanced=True, minimum=32.0, maximum=5000.0, step=16.0)
    good_fit_r2: float = setting(0.2, "Measuring", "Smallest fit quality (r²)", "Width, fitted peak and size are left empty "
                                 "when the fit explains less of the map than this.", "float", "", advanced=True,
                                 minimum=0.0, maximum=1.0, step=0.05)
    max_width_um: float = setting(380.0, "Measuring", "Largest width", "Width, fitted peak and size are left empty when the "
                                  "fitted width reaches this (the fit then describes the background, not the event).",
                                  "float", "µm", advanced=True, minimum=16.0, maximum=5000.0, step=10.0)

    # --- Tissue ---
    brightness_frames: list = setting([10, 95], "Tissue", "Resting brightness window", "Frames whose mean is each pixel's "
                                      "resting brightness (F0), used to find the tissue.", "frames", "frames", advanced=True)
    block_px: int = setting(4, "Tissue", "Block size", "The tissue is found in square blocks of this many pixels a side.",
                            "int", "pixels", advanced=True, minimum=1, maximum=64)
    dark_fraction: float = setting(0.3, "Tissue", "Leave out blocks darker than", "A block whose resting brightness is below "
                                   "this fraction of the median block's is not tissue.", "float", "× median", advanced=True,
                                   minimum=0.0, maximum=1.0, step=0.05)
    electrode_fraction: float = setting(0.5, "Tissue", "Leave out blocks under the electrode from", "A block is left out "
                                        "when at least this share of its pixels is under the electrode.", "float",
                                        "of the block", advanced=True, minimum=0.01, maximum=1.0, step=0.05)

    # --- Signal ---
    bleach_order: int = setting(4, "Signal", "Bleaching correction order", "Each pixel's brightness is divided by a "
                                "polynomial of this order fitted to it over time, which removes bleaching: "
                                "dF/F = F ÷ fit − 1.", "int", "", advanced=True, minimum=0, maximum=10)
    despike_frames: int = setting(3, "Signal", "Spike filter", "A running median over this many frames removes single-frame "
                                  "camera spikes. 1 switches it off.", "int", "frames", advanced=True, minimum=1, maximum=15)

    # --- Echoes ---
    echo_rule: bool = setting(True, "Echoes", "Drop echoes", "Filtering makes a dip just before and after each event. Of two "
                              "regions of opposite sign close in time and place, only the stronger counts.", "bool",
                              advanced=True)
    echo_ms: float = setting(533.0, "Echoes", "Close in time within", "Two regions are close in time when their onsets are at "
                             "most this far apart.", "float", "ms", advanced=True, minimum=0.0, maximum=10000.0, step=10.0)
    echo_um: float = setting(256.0, "Echoes", "Close in place within", "Two regions are close in place when their strongest "
                             "pixels are at most this far apart.", "float", "µm", advanced=True,
                             minimum=0.0, maximum=5000.0, step=16.0)
    echo_ratio: float = setting(1.0, "Echoes", "Stronger by at least", "A region is dropped when the other is at least this "
                                "many times as strong (1: the weaker of the two is dropped).", "float", "×", advanced=True,
                                minimum=0.1, maximum=10.0, step=0.05)

    def frames(self, ms):
        """A time in ms as a whole number of frames."""
        return int(round(ms / self.frame_ms))

    def pixels(self, um):
        """A distance in µm in pixels (not rounded)."""
        return um / self.pixel_um

    def problems(self):
        """Reasons these settings cannot be used, as sentences. Empty when they are fine."""
        found = []
        start, stop = self.brightness_frames
        if not 0 <= start < stop:
            found.append("Resting brightness window: the first frame must be smaller than the last.")
        if self.event_z < self.region_z:
            found.append("The event threshold must be at least the region threshold.")
        if self.despike_frames % 2 == 0:
            found.append("The spike filter needs an odd number of frames.")
        if self.after_ms <= self.frame_ms:
            found.append("The event shape must be longer than one frame after the onset.")
        return found
