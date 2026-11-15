"""The variables of ROI selection, with their defaults.

Each setting carries its own label, unit and help text. The settings dialog
and the documentation are both built from this one list.
"""

from dataclasses import asdict, dataclass, field, fields

EDGES = ["left", "right", "top", "bottom", "any"]


def setting(default, group, label, help, kind, unit="", **options):
    """One setting. `kind` picks its input widget: int, float, bool, names, frames or choice."""
    details = dict(group=group, label=label, help=help, kind=kind, unit=unit, **options)
    if isinstance(default, list):
        return field(default_factory=lambda: list(default), metadata=details)
    return field(default=default, metadata=details)


@dataclass
class RoiSettings:
    # --- ROI ---
    roi_radius_px: int = setting(
        20, "ROI", "ROI radius", "Radius of the circular ROI.", "int", "pixels", minimum=1, maximum=500
    )
    detection_files: list = setting(
        ["200uA", "300uA"],
        "ROI",
        "Recordings that set the ROI",
        "The automatic ROI is found on the mean response of these recordings (file names without "
        ".tif, separated by commas). A folder that has none of them uses every stimulated recording.",
        "names",
    )
    skip_words: list = setting(
        ["red"],
        "ROI",
        "Never use files named",
        "Recordings with one of these words in their name (for example 'hi1 red.tif') are left out "
        "of the automatic detection. They can still be viewed and flagged.",
        "names",
    )
    smoothing_px: float = setting(
        2.0,
        "ROI",
        "Smoothing",
        "Width (sigma) of the Gaussian blur applied to the response map before its maximum is "
        "taken. More smoothing ignores small bright spots.",
        "float",
        "pixels",
        minimum=0.0,
        maximum=20.0,
        step=0.5,
    )
    low_response_percent: float = setting(
        5.0,
        "ROI",
        "Low-response warning",
        "A folder is marked with a warning when the response at the automatic ROI is below this.",
        "float",
        "% dF/F",
        minimum=0.0,
        maximum=1000.0,
        step=1.0,
    )

    # --- Timing ---
    baseline_frames: list = setting(
        [10, 95],
        "Timing",
        "Baseline window",
        "Frames before the stimulation. Their mean is the resting brightness (F0) of each pixel.",
        "frames",
        "frames",
    )
    search_frames: list = setting(
        [95, 300],
        "Timing",
        "Response search window",
        "Frames in which the peak of the response is looked for.",
        "frames",
        "frames",
    )
    peak_frames_before: int = setting(
        2,
        "Timing",
        "Frames averaged before the peak",
        "The response map is the mean of a few frames around the peak.",
        "int",
        "frames",
        minimum=0,
        maximum=100,
    )
    peak_frames_after: int = setting(
        8,
        "Timing",
        "Frames averaged from the peak on",
        "Counted from the peak frame itself, so 8 means the peak and the 7 frames after it.",
        "int",
        "frames",
        minimum=1,
        maximum=100,
    )

    # --- Electrode ---
    find_electrode: bool = setting(
        True,
        "Electrode",
        "Find the electrode automatically",
        "Switch off to start every folder without an electrode mask.",
        "bool",
    )
    electrode_threshold: float = setting(
        0.90,
        "Electrode",
        "Darkness threshold",
        "A pixel may belong to the electrode when it is darker than this fraction of its "
        "surroundings. Lower values give a smaller mask.",
        "float",
        "× surroundings",
        minimum=0.1,
        maximum=1.0,
        step=0.01,
    )
    electrode_surround_px: int = setting(
        31,
        "Electrode",
        "Size of the surroundings",
        "Side of the square in which the typical (median) brightness around a pixel is measured. "
        "It should be clearly wider than the electrode.",
        "int",
        "pixels",
        minimum=3,
        maximum=255,
    )
    electrode_edge: str = setting(
        "left",
        "Electrode",
        "Electrode enters from",
        "The image edge the electrode comes in from.",
        "choice",
        choices=EDGES,
    )
    electrode_max_distance_px: int = setting(
        40,
        "Electrode",
        "Greatest distance from the ROI",
        "The electrode must come at least this close to the centre of the automatic ROI.",
        "int",
        "pixels",
        minimum=1,
        maximum=1000,
    )
    electrode_min_area_px: int = setting(
        100,
        "Electrode",
        "Smallest area",
        "Dark shapes with fewer pixels than this are not the electrode.",
        "int",
        "pixels",
        minimum=1,
        maximum=100000,
    )
    electrode_min_length_px: int = setting(
        30,
        "Electrode",
        "Smallest length",
        "Dark shapes shorter than this (corner to corner of their bounding box) are not the electrode.",
        "int",
        "pixels",
        minimum=1,
        maximum=1000,
    )
    electrode_grow_px: int = setting(
        1,
        "Electrode",
        "Grow the mask by",
        "The finished mask is widened by this many pixels to cover the blurred rim of the electrode.",
        "int",
        "pixels",
        minimum=0,
        maximum=20,
    )

    # --- Display ---
    pixel_size_um: float = setting(
        16.0,
        "Display",
        "Pixel size",
        "Only used to show sizes in micrometres. 16 µm is the 4× objective.",
        "float",
        "µm",
        minimum=0.01,
        maximum=1000.0,
        step=1.0,
    )

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, values):
        """Settings from a saved file. Names this version does not know are ignored."""
        known = {f.name for f in fields(cls)}
        return cls(**{name: value for name, value in values.items() if name in known})

    def problems(self):
        """Reasons these settings cannot be used, as sentences. Empty when they are fine."""
        found = []
        for name in ("baseline_frames", "search_frames"):
            start, stop = getattr(self, name)
            if not 0 <= start < stop:
                label = type(self).__dataclass_fields__[name].metadata["label"]
                found.append(f"{label}: the first frame must be smaller than the last.")
        if self.electrode_surround_px % 2 == 0:
            found.append("Size of the surroundings must be an odd number.")
        return found
