"""The built-in detectors, written as code, and the detector library.

After changing a built-in detector, run `python -m ema.spontaneous.presets` to
write them to `ema/spontaneous/built_in/` (a test checks that the files match
the code).
"""

from pathlib import Path

from ..library import Library, file_name
from ..paths import USER_DETECTORS
from .detector import Detector

BUILT_IN = Path(__file__).parent / "built_in"
LIBRARY = Library("detector", Detector.load, BUILT_IN, USER_DETECTORS)

STANDARD_EVENT = ["onset", "strength", "fitted peak", "width", "half-maximum area", "size", "local peak", "rise 10-90",
                  "half-decay", "distance to the ROI centre", "distance to the electrode"]
STANDARD_RECORDING = ["events", "searched time", "rate", "tissue area", "density", "sign-flipped", "time-reversed"]
STANDARD_SLICE = ["events", "searched time", "rate", "density", "sign-flipped rate", "time-reversed rate",
                  "rate above the sign-flip floor", "share near the ROI centre", "share on the electrode side",
                  "release per minute"]
STANDARD_SLICE_OF_EVENTS = ["fitted peak", "width", "rise 10-90", "half-decay", "size"]


def standard_detector():
    return Detector(
        "Standard detector",
        "Finds dLight events at least 8 times the noise, after pooling pixels over 128 µm and filtering with the shape of a "
        "dLight event. Its settings are the defaults.",
        event_measures=list(STANDARD_EVENT), recording_measures=list(STANDARD_RECORDING),
        slice_measures=list(STANDARD_SLICE), slice_event_measures=list(STANDARD_SLICE_OF_EVENTS),
    )


PRESETS = [standard_detector]


def write_presets():
    BUILT_IN.mkdir(exist_ok=True)
    for make in PRESETS:
        detector = make()
        assert not detector.problems(), detector.problems()
        detector.save(BUILT_IN / file_name(detector.name))
        print("wrote", file_name(detector.name))


if __name__ == "__main__":
    write_presets()
