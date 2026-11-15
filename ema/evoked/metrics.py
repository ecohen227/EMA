"""The catalogue of kinetic and spatial measures, and the settings of the spatial ones.

Every measure is described once here. The configurator's Kinetics and
Spatial tabs, the list of what a protocol measures and the documentation are
all built from these lists, so a new measure is added by adding an entry here
and computing it in kinetics.py or spatial.py.
"""

from dataclasses import asdict, dataclass, field, fields


@dataclass(frozen=True)
class Metric:
    key: str  # its name in a protocol file, and in the name of the measure ("P1 <key>")
    unit: str
    group: str
    explanation: str  # "{pulse}" is replaced by the pulse's name


KINETIC = [
    Metric("time to peak", "ms", "Timing", "Time from the stimulus of {pulse} to the maximum of its response."),
    Metric("onset", "ms", "Timing", "Time from the stimulus of {pulse} until its response first reaches 20 % of its maximum."),
    Metric("rise 10-90", "ms", "Rise", "Time the response of {pulse} takes to rise from 10 % to 90 % of its maximum."),
    Metric("rise 20-80", "ms", "Rise", "Time the response of {pulse} takes to rise from 20 % to 80 % of its maximum."),
    Metric("max rise slope", "%/s", "Rise", "The steepest rise of the response of {pulse}, in percent per second."),
    Metric("half-width", "ms", "Duration and decay", "Time the response of {pulse} stays above half of its maximum."),
    Metric("half-decay", "ms", "Duration and decay", "Time from the maximum of {pulse} until its response has fallen to half of it."),
    Metric("1/e decay", "ms", "Duration and decay", "Time from the maximum of {pulse} until its response has fallen to 1/e (37 %) of it."),
    Metric("max decay slope", "%/s", "Duration and decay", "The steepest fall of the response of {pulse} after its maximum, in percent per second (a positive number)."),
    Metric("area", "%·s", "Size", "Area under the response of {pulse}, from its stimulus to the end of its peak window."),
    Metric("signal-to-noise", "ratio", "Size", "Maximum of the response of {pulse} ÷ the standard deviation of the response in its baseline window."),
]

SPATIAL = [
    Metric("footprint width", "µm", "Footprint size",
           "Width λ of a/(1 + (r/λ)²) + c fitted to the ring averages of the response map of {pulse} around the ROI centre. "
           "Empty when the fit fails or λ is outside 11 to 4999 µm."),
    Metric("footprint half-width", "µm", "Footprint size",
           "Distance from the ROI centre at which the ring average of the map of {pulse} first falls below half of its "
           "largest value within the first three rings."),
    Metric("r50", "µm", "Footprint size",
           "Radius of the circle around the ROI centre that holds half of the signal of the map of {pulse} "
           "within the integration radius."),
    Metric("tail fraction", "fraction", "Footprint size",
           "Share of the signal of the map of {pulse}, within the integration radius, that lies beyond the tail radius."),
    Metric("centroid offset", "µm", "Centroid and unevenness",
           "Distance from the ROI centre to the signal-weighted centre of the map of {pulse} within the region radius. "
           "Electrode pixels count as the average of their ring."),
    Metric("heterogeneity", "fraction", "Centroid and unevenness",
           "How uneven the map of {pulse} is around its ring averages within the region radius, with the noise taken "
           "out: √(variance of the residuals − variance of a noise map) ÷ mean signal."),
    Metric("elongation", "ratio", "Centroid and unevenness",
           "How stretched the map of {pulse} is within the region radius: √(largest ÷ smallest spread along two "
           "perpendicular axes) of its signal-weighted second moments. 1 for a round footprint."),
    Metric("hot spots", "per mm²", "Centroid and unevenness",
           "Local maxima of the residual map of {pulse} (map minus ring averages) more than 3 noise SDs high, per mm², "
           "within the region radius."),
    Metric("latency slope", "ms/mm", "Release spread",
           "How much later release starts further from the ROI centre: Theil–Sen slope of the median half-rise "
           "latency of each ring against its distance, for {pulse}."),
    Metric("far-near delay", "ms", "Release spread",
           "Median half-rise latency in the far band minus that in the near band, for {pulse}."),
    Metric("far-near decay ratio", "ratio", "Decay with distance",
           "Half-decay time of the far band of {pulse} ÷ that of the near band, both from the peak. "
           "Below 1 when the response far from the centre fades faster."),
    Metric("decay-distance slope", "ms/mm", "Decay with distance",
           "How the half-decay time of each ring of {pulse} changes with its distance from the ROI centre: "
           "Theil–Sen slope, out to the end of the far band. Negative when far rings fade faster."),
]

NEAR_TO_FAR = Metric(
    "near-to-far", "ratio", "Near-to-far index",
    "The comparison {pulse} measured on the response maps in the far band, divided by the same in the near band. "
    "Below 1 when the later pulse is relatively weaker far from the centre.",
)

KINETIC_KEYS = [m.key for m in KINETIC]
SPATIAL_KEYS = [m.key for m in SPATIAL]


def metric(key):
    return next(m for m in KINETIC + SPATIAL if m.key == key)


def setting(default, label, help, unit="", minimum=0.0, maximum=10000.0, step=1.0, kind="float"):
    return field(default=default, metadata=dict(label=label, help=help, unit=unit, minimum=minimum,
                                                maximum=maximum, step=step, kind=kind))


@dataclass
class SpatialSettings:
    """How the response maps are made and the rings around the ROI centre are measured."""

    frames_before_peak: int = setting(1, "Frames before the peak", "The response map averages the frames around the peak of the ROI trace: this many before it…", "frames", 0, 100, 1, "int")
    frames_from_peak: int = setting(4, "Frames from the peak on", "…and this many from the peak on (the peak frame included).", "frames", 1, 100, 1, "int")
    smoothing_px: float = setting(1.0, "Spatial smoothing", "Width (sigma) of the Gaussian blur of the map. 0 means none.", "px", 0, 20, 0.5)
    pixel_um: float = setting(16.0, "Pixel size", "Size of one pixel in the slice. 16 µm with the 4× objective.", "µm", 0.01, 1000, 1)
    max_radius_um: float = setting(960.0, "Largest ring", "Rings around the ROI centre are measured out to this distance. Rings less than 25 % inside the image are left out.", "µm", 16, 5000, 16)
    integrate_um: float = setting(640.0, "Integration radius", "r50 and the tail fraction use the signal within this distance.", "µm", 16, 5000, 16)
    tail_from_um: float = setting(320.0, "Tail radius", "The tail fraction is the signal beyond this distance.", "µm", 16, 5000, 16)
    region_um: float = setting(480.0, "Region radius", "Centroid, heterogeneity and hot spots use the map within this distance.", "µm", 16, 5000, 16)
    near_from_um: float = setting(0.0, "Near band from", "The near band of the near-to-far index and the release delay…", "µm", 0, 5000, 16)
    near_to_um: float = setting(160.0, "Near band up to", "…ends here.", "µm", 0, 5000, 16)
    far_from_um: float = setting(400.0, "Far band from", "The far band starts here…", "µm", 0, 5000, 16)
    far_to_um: float = setting(640.0, "Far band up to", "…and ends here.", "µm", 0, 5000, 16)
    exclude_electrode: bool = setting(True, "Leave out the electrode", "Pixels under the stimulating electrode (from ROI Selection) are left out of ring averages and residuals.", kind="bool")
    follow_ms: float = setting(1500.0, "Follow the decay for at most", "The decay with distance is followed from the peak for at most this long, and never past the next stimulus or the end of the recording.", "ms", 50, 20000, 50)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, values):
        known = {f.name for f in fields(cls)}
        return cls(**{name: value for name, value in values.items() if name in known})

    def problems(self):
        found = []
        if self.near_from_um >= self.near_to_um or self.far_from_um >= self.far_to_um:
            found.append("Each spatial band must end after it starts.")
        if self.near_to_um > self.far_from_um:
            found.append("The near band must end before the far band starts.")
        if self.tail_from_um >= self.integrate_um:
            found.append("The tail radius must be smaller than the integration radius.")
        return found
