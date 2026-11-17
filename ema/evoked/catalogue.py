"""The catalogue of kinetic and spatial measures, and the settings of the spatial ones.

Every measure is described once here. The configurator's Kinetics and Spatial
tabs, the list of what a protocol measures and the documentation are all built
from these lists. To add a measure, see "Extending EMA" in the documentation.
"""

from dataclasses import dataclass

from ..definitions import Measure, Settings, setting
from ..recordings import PIXEL_UM

# "{pulse}" in an explanation is replaced by the pulse's name.
KINETIC = [
    Measure("time to peak", "ms", "Timing", "Time from the stimulus of {pulse} to the maximum of its response."),
    Measure("onset", "ms", "Timing", "Time from the stimulus of {pulse} until its response first reaches 20 % of its maximum."),
    Measure("rise 10-90", "ms", "Rise", "Time the response of {pulse} takes to rise from 10 % to 90 % of its maximum."),
    Measure("rise 20-80", "ms", "Rise", "Time the response of {pulse} takes to rise from 20 % to 80 % of its maximum."),
    Measure("max rise slope", "%/s", "Rise", "The steepest rise of the response of {pulse}, in percent per second."),
    Measure("half-width", "ms", "Duration and decay", "Time the response of {pulse} stays above half of its maximum."),
    Measure("half-decay", "ms", "Duration and decay", "Time from the maximum of {pulse} until its response has fallen to half of it."),
    Measure("1/e decay", "ms", "Duration and decay", "Time from the maximum of {pulse} until its response has fallen to 1/e (37 %) of it."),
    Measure("max decay slope", "%/s", "Duration and decay", "The steepest fall of the response of {pulse} after its maximum, in percent per second (a positive number)."),
    Measure("area", "%·s", "Size", "Area under the response of {pulse}, from its stimulus to the end of its peak window."),
    Measure("signal-to-noise", "ratio", "Size", "Maximum of the response of {pulse} ÷ the standard deviation of the response in its baseline window."),
]

SPATIAL = [
    Measure("footprint width", "µm", "Footprint size",
           "Width λ of a/(1 + (r/λ)²) + c fitted to the ring averages of the response map of {pulse} around the ROI centre. "
           "Empty when the fit fails or λ is outside 11 to 4999 µm."),
    Measure("footprint half-width", "µm", "Footprint size",
           "Distance from the ROI centre at which the ring average of the map of {pulse} first falls below half of its "
           "largest value within the first three rings."),
    Measure("r50", "µm", "Footprint size",
           "Radius of the circle around the ROI centre that holds half of the signal of the map of {pulse} "
           "within the integration radius."),
    Measure("tail fraction", "fraction", "Footprint size",
           "Share of the signal of the map of {pulse}, within the integration radius, that lies beyond the tail radius."),
    Measure("centroid offset", "µm", "Centroid and unevenness",
           "Distance from the ROI centre to the signal-weighted centre of the map of {pulse} within the region radius. "
           "Electrode pixels count as the average of their ring."),
    Measure("heterogeneity", "fraction", "Centroid and unevenness",
           "How uneven the map of {pulse} is around its ring averages within the region radius, with the noise taken "
           "out: √(variance of the residuals − variance of a noise map) ÷ mean signal."),
    Measure("elongation", "ratio", "Centroid and unevenness",
           "How stretched the map of {pulse} is within the region radius: √(largest ÷ smallest spread along two "
           "perpendicular axes) of its signal-weighted second moments. 1 for a round footprint."),
    Measure("hot spots", "per mm²", "Centroid and unevenness",
           "Local maxima of the residual map of {pulse} (map minus ring averages) more than 3 noise SDs high, per mm², "
           "within the region radius."),
    Measure("latency slope", "ms/mm", "Release spread",
           "How much later release starts further from the ROI centre: Theil–Sen slope of the median half-rise "
           "latency of each ring against its distance, for {pulse}."),
    Measure("far-near delay", "ms", "Release spread",
           "Median half-rise latency in the far band minus that in the near band, for {pulse}."),
    Measure("far-near decay ratio", "ratio", "Decay with distance",
           "Half-decay time of the far band of {pulse} ÷ that of the near band, both from the peak. "
           "Below 1 when the response far from the centre fades faster."),
    Measure("decay-distance slope", "ms/mm", "Decay with distance",
           "How the half-decay time of each ring of {pulse} changes with its distance from the ROI centre: "
           "Theil–Sen slope, out to the end of the far band. Negative when far rings fade faster."),
]

NEAR_TO_FAR = Measure(
    "near-to-far", "ratio", "Near-to-far index",
    "The comparison {pulse} measured on the response maps in the far band, divided by the same in the near band. "
    "Below 1 when the later pulse is relatively weaker far from the centre.",
)

KINETIC_KEYS = [m.key for m in KINETIC]
SPATIAL_KEYS = [m.key for m in SPATIAL]


def metric(key):
    return next(m for m in KINETIC + SPATIAL if m.key == key)


def _spatial(default, label, help, unit="", minimum=0.0, maximum=10000.0, step=1.0, kind="float"):
    if kind == "bool":
        return setting(default, "Maps and rings", label, help, kind)
    return setting(default, "Maps and rings", label, help, kind, unit, minimum=minimum, maximum=maximum, step=step)


@dataclass
class SpatialSettings(Settings):
    """How the response maps are made and the rings around the ROI centre are measured."""

    frames_before_peak: int = _spatial(1, "Frames before the peak", "The response map averages the frames around the peak of the ROI trace: this many before it…", "frames", 0, 100, 1, "int")
    frames_from_peak: int = _spatial(4, "Frames from the peak on", "…and this many from the peak on (the peak frame included).", "frames", 1, 100, 1, "int")
    smoothing_px: float = _spatial(1.0, "Spatial smoothing", "Width (sigma) of the Gaussian blur of the map. 0 means none.", "px", 0, 20, 0.5)
    pixel_um: float = _spatial(PIXEL_UM, "Pixel size", "Size of one pixel in the slice. 16 µm with the 4× objective.", "µm", 0.01, 1000, 1)
    max_radius_um: float = _spatial(960.0, "Largest ring", "Rings around the ROI centre are measured out to this distance. Rings less than 25 % inside the image are left out.", "µm", 16, 5000, 16)
    integrate_um: float = _spatial(640.0, "Integration radius", "r50 and the tail fraction use the signal within this distance.", "µm", 16, 5000, 16)
    tail_from_um: float = _spatial(320.0, "Tail radius", "The tail fraction is the signal beyond this distance.", "µm", 16, 5000, 16)
    region_um: float = _spatial(480.0, "Region radius", "Centroid, heterogeneity and hot spots use the map within this distance.", "µm", 16, 5000, 16)
    near_from_um: float = _spatial(0.0, "Near band from", "The near band of the near-to-far index and the release delay…", "µm", 0, 5000, 16)
    near_to_um: float = _spatial(160.0, "Near band up to", "…ends here.", "µm", 0, 5000, 16)
    far_from_um: float = _spatial(400.0, "Far band from", "The far band starts here…", "µm", 0, 5000, 16)
    far_to_um: float = _spatial(640.0, "Far band up to", "…and ends here.", "µm", 0, 5000, 16)
    exclude_electrode: bool = _spatial(True, "Leave out the electrode", "Pixels under the stimulating electrode (from ROI Selection) are left out of ring averages and residuals.", kind="bool")
    follow_ms: float = _spatial(1500.0, "Follow the decay for at most", "The decay with distance is followed from the peak for at most this long, and never past the next stimulus or the end of the recording.", "ms", 50, 20000, 50)

    def problems(self):
        found = []
        if self.near_from_um >= self.near_to_um or self.far_from_um >= self.far_to_um:
            found.append("Each spatial band must end after it starts.")
        if self.near_to_um > self.far_from_um:
            found.append("The near band must end before the far band starts.")
        if self.tail_from_um >= self.integrate_um:
            found.append("The tail radius must be smaller than the integration radius.")
        return found
