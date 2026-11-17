"""A detector: everything the spontaneous-event analysis needs to know to search and measure recordings.

It holds the detector's settings (see settings.py), which recordings of a
folder are searched (the unstimulated ones, named 'no' and a number, without
the skip words), and which measures are reported per event, per recording and
per slice. It is saved as a JSON file; the built-in detectors and the library
are in presets.py.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..recordings import has_skip_word, is_no_stim
from .catalogue import EVENT, EVENT_KEYS, RECORDING, RECORDING_KEYS, RENAMED, SLICE, SLICE_KEYS, STATISTICS
from .settings import DetectorSettings

FORMAT = "EMA spontaneous detector"
FORMAT_VERSION = 1


class DetectorError(ValueError):
    pass


@dataclass
class Detector:
    name: str
    description: str = ""
    settings: DetectorSettings = field(default_factory=DetectorSettings)
    skip_words: list = field(default_factory=lambda: ["red"])
    event_measures: list = field(default_factory=list)  # keys of catalogue.EVENT
    recording_measures: list = field(default_factory=list)  # keys of catalogue.RECORDING
    slice_measures: list = field(default_factory=list)  # keys of catalogue.SLICE
    slice_statistics: list = field(default_factory=lambda: ["median"])  # summaries of the event measures per slice
    slice_event_measures: list = field(default_factory=list)  # the event measures summarised per slice

    def searched_files(self, paths):
        """The recordings of a folder that are searched: the unstimulated ones without a skip word."""
        return [path for path in paths if is_no_stim(path) and not has_skip_word(path, self.skip_words)]

    def event_columns(self):
        """The chosen per-event measures (catalogue entries), in catalogue order."""
        return [m for m in EVENT if m.key in self.event_measures]

    def recording_columns(self):
        """The chosen per-recording measures (catalogue entries), in catalogue order."""
        return [m for m in RECORDING if m.key in self.recording_measures]

    def slice_columns(self):
        """(name, unit, explanation) of every per-slice measure reported: the chosen ones, then the summaries of event
        measures, such as 'width median'."""
        chosen = [(m.key, m.unit, m.explanation) for m in SLICE if m.key in self.slice_measures]
        units = {m.key: m.unit for m in EVENT}
        for key in self.slice_event_measures:
            for statistic in self.slice_statistics:
                chosen.append((f"{key} {statistic}", units[key], f"The {statistic} of the slice's events' {key}."))
        return chosen

    def problems(self):
        """What is wrong with the detector, as sentences. Empty when it can be used."""
        found = list(self.settings.problems())
        if not self.name.strip():
            found.append("The detector needs a name.")
        unknown = (set(self.event_measures) - set(EVENT_KEYS)) | (set(self.recording_measures) - set(RECORDING_KEYS)) | (
            set(self.slice_measures) - set(SLICE_KEYS)) | (set(self.slice_event_measures) - set(EVENT_KEYS)) | (
            set(self.slice_statistics) - set(STATISTICS))
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
        """A detector from a saved file. Raises DetectorError when it is not a detector or is damaged."""
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise DetectorError("This is not an EMA spontaneous detector file.")
        if data.get("format_version", 1) > FORMAT_VERSION:
            raise DetectorError("This detector was saved by a newer version of EMA.")
        try:
            measures = data.get("measures", {})
            of_events = measures.get("per_slice_of_events", {})
            return cls(
                name=str(data["name"]),
                description=str(data.get("description", "")),
                settings=DetectorSettings.from_dict(data.get("settings", {})),
                skip_words=[str(word) for word in data.get("recordings", {}).get("skip_words", [])],
                event_measures=_keys(measures.get("per_event", [])),
                recording_measures=_keys(measures.get("per_recording", [])),
                slice_measures=_keys(measures.get("per_slice", [])),
                slice_statistics=[str(s) for s in of_events.get("statistics", ["median"])],
                slice_event_measures=_keys(of_events.get("measures", [])),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise DetectorError(f"The detector file is incomplete or damaged ({error}).") from error

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path):
        """Read a detector file. Raises OSError, or DetectorError when it is not a detector or is damaged."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except ValueError as error:  # not JSON, or not UTF-8 text
            raise DetectorError(f"{Path(path).name} is not a valid JSON file ({error}).") from error
        return cls.from_dict(data)


def _keys(keys):
    """Measure keys from a file, with keys renamed since then brought up to date."""
    return [RENAMED.get(str(key), str(key)) for key in keys]
