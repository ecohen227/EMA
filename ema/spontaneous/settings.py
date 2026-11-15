"""The settings of the spontaneous-event detector, with the values of detector v5 as defaults.

Each setting carries its label, unit, group and help text. The configurator's
form and the documentation's tables are both built from this one list.
Times are given in ms and distances in µm; the detector converts them to
frames and pixels with the frame interval and the pixel size.
"""

from dataclasses import asdict, dataclass, fields

from ..roi_selection.settings import setting

GROUPS = ("Movie", "Tissue", "Signal", "Template", "Spatial filter", "Detection", "Echoes", "Controls", "Measuring")


@dataclass
class DetectorSettings:
    # --- Movie ---
    frame_ms: float = setting(4.849, "Movie", "Frame interval", "The time between two frames.", "float", "ms",
                              minimum=0.001, maximum=10000.0, step=0.001)
    pixel_um: float = setting(16.0, "Movie", "Pixel size", "The width of one pixel in the slice (16 µm with the 4× objective).",
                              "float", "µm", minimum=0.01, maximum=1000.0, step=1.0)
    first_frames: int = setting(20, "Movie", "Leave out the first", "Frames left out at the start of each recording, "
                                "counted after the first frame of the file (which EMA always drops).", "int", "frames",
                                minimum=0, maximum=100000)
    last_frames: int = setting(10, "Movie", "Leave out the last", "Frames left out at the end of each recording.", "int",
                               "frames", minimum=0, maximum=100000)

    # --- Tissue ---
    brightness_frames: list = setting([10, 95], "Tissue", "Resting brightness window", "Frames whose mean is each pixel's "
                                      "resting brightness (F0), used to find the tissue.", "frames", "frames")
    block_px: int = setting(4, "Tissue", "Block size", "The tissue is found in square blocks of this many pixels a side.",
                            "int", "pixels", minimum=1, maximum=64)
    dark_fraction: float = setting(0.3, "Tissue", "Leave out blocks darker than", "A block whose resting brightness is below "
                                   "this fraction of the median block's is not tissue.", "float", "× median",
                                   minimum=0.0, maximum=1.0, step=0.05)
    electrode_fraction: float = setting(0.5, "Tissue", "Leave out blocks under the electrode from", "A block is left out "
                                        "when at least this share of its pixels is under the electrode mask of the ROI file.",
                                        "float", "of the block", minimum=0.01, maximum=1.0, step=0.05)

    # --- Signal ---
    bleach_order: int = setting(4, "Signal", "Bleaching fit order", "Each pixel's brightness is divided by a polynomial of "
                                "this order fitted to it over time, which removes bleaching: dF/F = F ÷ fit − 1.",
                                "int", "", minimum=0, maximum=10)
    despike_frames: int = setting(3, "Signal", "Spike filter", "A running median over this many frames removes single-frame "
                                  "camera spikes. 1 switches it off.", "int", "frames", minimum=1, maximum=15)

    # --- Template ---
    rise_ms: float = setting(12.0, "Template", "Rise time constant", "The rise of the event template, A·(exp(−t/decay) − "
                             "exp(−t/rise)).", "float", "ms", minimum=0.1, maximum=10000.0, step=1.0)
    decay_ms: float = setting(200.0, "Template", "Decay time constant", "The decay of the event template.", "float", "ms",
                              minimum=0.1, maximum=10000.0, step=10.0)
    before_ms: float = setting(100.0, "Template", "Baseline before the onset", "How much of the trace before an onset the "
                               "template covers.", "float", "ms", minimum=0.0, maximum=10000.0, step=10.0)
    after_ms: float = setting(600.0, "Template", "Length after the onset", "How much of the trace after an onset the template "
                              "covers.", "float", "ms", minimum=10.0, maximum=10000.0, step=10.0)
    line_baseline: bool = setting(True, "Template", "Fit a sloping baseline", "The template is fitted together with a "
                                  "straight line, so a slow drift under an event does not change its score.", "bool")

    # --- Spatial filter ---
    blur_um: float = setting(128.0, "Spatial filter", "Width (σ)", "The Gaussian that pools neighbouring pixels. About the "
                             "width of a typical event (σ ≈ 150 µm) finds the most events; 64 µm is better for small ones.",
                             "float", "µm", minimum=0.0, maximum=2000.0, step=16.0)
    remove_field: bool = setting(True, "Spatial filter", "Remove the field-wide signal", "Each filtered frame's median over "
                                 "the tissue is subtracted, which removes changes shared by the whole field.", "bool")

    # --- Detection ---
    region_z: float = setting(3.0, "Detection", "Region threshold", "Neighbouring pixels and frames with a z of at least this "
                              "form one region; each region is one candidate event.", "float", "z",
                              minimum=0.5, maximum=100.0, step=0.5)
    event_z: float = setting(8.0, "Detection", "Event threshold (θ)", "A region whose largest z reaches this is an event.",
                             "float", "z", minimum=1.0, maximum=100.0, step=0.5)
    end_trim_ms: float = setting(320.0, "Detection", "Leave out onsets in the last", "Onsets this close to the end of the "
                                 "searched part are not counted: there the template reaches the last frames, where the "
                                 "bleaching fit is least certain.", "float", "ms", minimum=0.0, maximum=10000.0, step=10.0)

    # --- Echoes ---
    echo_rule: bool = setting(True, "Echoes", "Drop echoes", "The template's response to an event dips before and after it. "
                              "Of two regions of opposite sign close in time and place, only the stronger counts.", "bool")
    echo_ms: float = setting(533.0, "Echoes", "Close in time within", "Two regions are close in time when their onsets are at "
                             "most this far apart. The template's echoes reach 0.35 s before and 0.13 s after an event; with "
                             "its 0.1 s baseline, 0.53 s covers both.", "float", "ms", minimum=0.0, maximum=10000.0, step=10.0)
    echo_um: float = setting(256.0, "Echoes", "Close in place within", "Two regions are close in place when their maxima are at "
                             "most this far apart (twice the spatial filter's width).", "float", "µm",
                             minimum=0.0, maximum=5000.0, step=16.0)
    echo_ratio: float = setting(1.0, "Echoes", "Stronger by at least", "A region is dropped when the other is at least this "
                                "many times as strong (1: the weaker of the two is dropped).", "float", "×",
                                minimum=0.1, maximum=10.0, step=0.05)

    # --- Controls ---
    sign_flip: bool = setting(True, "Controls", "Count sign-flipped detections", "The detector also searches the movie "
                              "turned upside down (dips instead of rises). Those detections estimate the false positives.",
                              "bool")
    time_reversed: bool = setting(True, "Controls", "Count time-reversed detections", "The detector also searches the movie "
                                  "played backwards. Real events, with a fast rise and slow decay, mostly disappear.", "bool")

    # --- Measuring ---
    fit_radius_um: float = setting(400.0, "Measuring", "Fit the width within", "The Gaussian that measures an event's width "
                                   "and peak is fitted to the pixels within this distance of the event.", "float", "µm",
                                   minimum=32.0, maximum=5000.0, step=16.0)
    good_fit_r2: float = setting(0.2, "Measuring", "Smallest fit quality (r²)", "Width, fitted peak and size are left empty "
                                 "when the fit explains less of the map than this.", "float", "", minimum=0.0, maximum=1.0,
                                 step=0.05)
    max_width_um: float = setting(380.0, "Measuring", "Largest width", "Width, fitted peak and size are left empty when the "
                                  "fitted σ reaches this (the fit then describes the background, not the event).", "float",
                                  "µm", minimum=16.0, maximum=5000.0, step=10.0)
    near_um: float = setting(480.0, "Measuring", "Near the release centre within", "For the share of events near the release "
                             "centre (the ROI centre).", "float", "µm", minimum=0.0, maximum=5000.0, step=16.0)
    site_um: float = setting(100.0, "Measuring", "Same site within", "Events closer than this are counted as the same site, "
                             "for the recurring-site measures.", "float", "µm", minimum=1.0, maximum=5000.0, step=10.0)
    together_ms: float = setting(1000.0, "Measuring", "Together within", "Two events of a recording closer in time than "
                                 "this count as together, for the share of events together.", "float", "ms",
                                 minimum=1.0, maximum=60000.0, step=100.0)

    def frames(self, ms):
        """A time in ms as a whole number of frames."""
        return int(round(ms / self.frame_ms))

    def pixels(self, um):
        """A distance in µm in pixels (not rounded)."""
        return um / self.pixel_um

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, values):
        """Settings from a saved file. Names this version does not know are ignored; missing ones take their default."""
        known = {f.name for f in fields(cls)}
        return cls(**{name: value for name, value in values.items() if name in known})

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
            found.append("The template must be longer than one frame after the onset.")
        return found
