"""A detector: everything the spontaneous-event analysis needs to know to search and measure recordings.

It holds the detector's settings (see settings.py), which recordings of a
folder are searched (the unstimulated ones, named 'no' and a number, without
the skip words), and which measures are reported per event, per recording
and per slice. It is saved as a JSON file; the built-in detectors are in
`presets/` and the user's in the `detectors` folder of the EMA program
folder, like the evoked protocols.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..recordings import is_no_stim
from .measures import EVENT_KEYS, RECORDING_KEYS, SLICE_KEYS, STATISTICS
from .settings import DetectorSettings

FORMAT = "EMA spontaneous detector"
FORMAT_VERSION = 1
PRESETS_FOLDER = Path(__file__).parent / "presets"
USER_FOLDER = Path(__file__).resolve().parents[2] / "detectors"


class DetectorError(ValueError):
    pass


@dataclass
class Detector:
    name: str
    description: str = ""
    settings: DetectorSettings = field(default_factory=DetectorSettings)
    skip_words: list = field(default_factory=lambda: ["red"])
    event_measures: list = field(default_factory=list)  # keys of measures.EVENT
    recording_measures: list = field(default_factory=list)  # keys of measures.RECORDING
    slice_measures: list = field(default_factory=list)  # keys of measures.SLICE
    slice_statistics: list = field(default_factory=lambda: ["median"])  # summaries of the event measures per slice
    slice_event_measures: list = field(default_factory=list)  # the event measures summarised per slice

    def searched_files(self, paths):
        """The recordings of a folder that are searched: the unstimulated ones without a skip word."""
        skip = {word.lower() for word in self.skip_words}
        return [path for path in paths if is_no_stim(path) and not skip & set(re.split(r"[\s_\-]+", Path(path).stem.lower()))]

    def slice_measure_names(self):
        """Every per-slice measure, in order: the chosen ones, then the summaries of event measures."""
        summaries = [f"{key} {statistic}" for key in self.slice_event_measures for statistic in self.slice_statistics]
        return [key for key in SLICE_KEYS if key in self.slice_measures] + summaries

    def problems(self):
        """What is wrong with the detector, as sentences. Empty when it can be used."""
        found = list(self.settings.problems())
        if not self.name.strip():
            found.append("The detector needs a name.")
        unknown = (set(self.event_measures) - set(EVENT_KEYS)) | (set(self.recording_measures) - set(RECORDING_KEYS)) | (
            set(self.slice_measures) - set(SLICE_KEYS)) | (set(self.slice_statistics) - set(STATISTICS))
        if unknown:
            found.append("Unknown measures: " + ", ".join(sorted(unknown)) + ".")
        return found

    def to_dict(self):
        return {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "name": self.name,
            "description": self.description,
            "recordings": {"searched": "unstimulated recordings", "skip_words": self.skip_words},
            "settings": self.settings.to_dict(),
            "measures": {
                "per_event": self.event_measures,
                "per_recording": self.recording_measures,
                "per_slice": self.slice_measures,
                "per_slice_of_events": {"measures": self.slice_event_measures, "statistics": self.slice_statistics},
            },
        }

    @classmethod
    def from_dict(cls, data):
        if data.get("format") != FORMAT:
            raise DetectorError("This is not an EMA spontaneous detector file.")
        if data.get("format_version", 1) > FORMAT_VERSION:
            raise DetectorError("This detector was saved by a newer version of EMA.")
        measures = data.get("measures", {})
        of_events = measures.get("per_slice_of_events", {})
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            settings=DetectorSettings.from_dict(data.get("settings", {})),
            skip_words=list(data.get("recordings", {}).get("skip_words", [])),
            event_measures=list(measures.get("per_event", [])),
            recording_measures=list(measures.get("per_recording", [])),
            slice_measures=list(measures.get("per_slice", [])),
            slice_statistics=list(of_events.get("statistics", ["median"])),
            slice_event_measures=list(of_events.get("measures", [])),
        )

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise DetectorError(f"{Path(path).name} cannot be read: {error}") from error
        return cls.from_dict(data)


# ---------------------------------------------------------------------------
# The built-in detectors
# ---------------------------------------------------------------------------

V5_EVENT = ["onset", "z", "fitted peak", "width", "half-maximum area", "size", "local peak", "rise 10-90", "half-decay",
            "distance to the release centre", "distance to the electrode"]
V5_RECORDING = ["events", "searched time", "rate", "tissue area", "density", "sign-flipped", "time-reversed"]
V5_SLICE = ["events", "searched time", "rate", "density", "sign-flipped rate", "time-reversed rate",
            "rate above the sign-flip floor", "share near the release centre", "share on the electrode side",
            "release per minute"]
V5_SLICE_OF_EVENTS = ["fitted peak", "width", "rise 10-90", "half-decay", "size"]


def detector_v5():
    return Detector(
        "Detector v5",
        "The detector of the metric study (13–14 Nov 2026): a 128 µm Gaussian and the dLight template as a matched filter, "
        "events at z ≥ 8, the echo rule (ratio 1) and the end trim. About 7 events per minute per 2 mm field; sign-flipped "
        "detections about 7 % of events.",
        event_measures=list(V5_EVENT), recording_measures=list(V5_RECORDING), slice_measures=list(V5_SLICE),
        slice_event_measures=list(V5_SLICE_OF_EVENTS),
    )


PRESETS = [detector_v5]


def file_name(name):
    cleaned = re.sub(r'[<>:"/\\|?*]', "-", name).strip(" .")
    return f"{cleaned or 'detector'}.json"


def write_presets():
    """Write the built-in detectors to presets/. Run `python -m ema.spontaneous.detector` after changing them."""
    PRESETS_FOLDER.mkdir(exist_ok=True)
    for make in PRESETS:
        detector = make()
        assert not detector.problems(), detector.problems()
        detector.save(PRESETS_FOLDER / file_name(detector.name))
        print("wrote", file_name(detector.name))


@dataclass
class Entry:
    """A detector in the library: where its file is, and whether it is built in."""

    name: str
    path: Path
    built_in: bool

    @property
    def label(self):
        return f"{self.name}  (built in)" if self.built_in else self.name

    def load(self):
        return Detector.load(self.path)


def entries(user_folder=None):
    """Every detector in the library: built-in ones first, then saved ones, each by name."""
    found = sorted((Entry(Detector.load(p).name, p, True) for p in PRESETS_FOLDER.glob("*.json")), key=lambda e: e.name.lower())
    folder = user_folder or USER_FOLDER
    if folder.is_dir():
        saved = []
        for path in folder.glob("*.json"):
            try:
                saved.append(Entry(Detector.load(path).name, path, False))
            except DetectorError:
                continue  # a damaged or foreign file is left alone
        found += sorted(saved, key=lambda e: e.name.lower())
    return found


def is_taken(name, user_folder=None, except_path=None):
    return any(e.name.lower() == name.strip().lower() and e.path != except_path for e in entries(user_folder))


def save_in_library(detector, user_folder=None, replacing=None):
    """Save a detector into the library and return its path; `replacing` is the saved file it replaces."""
    folder = user_folder or USER_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file_name(detector.name)
    detector.save(path)
    if replacing is not None and Path(replacing) != path and Path(replacing).parent == folder:
        Path(replacing).unlink(missing_ok=True)
    return path


if __name__ == "__main__":
    write_presets()
