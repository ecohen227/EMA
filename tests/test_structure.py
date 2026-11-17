"""Rules of the code base that keep it safe to change: what the tests here check is easy to forget by hand."""

import ast
import json
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from ema.definitions import KINDS, Settings
from ema.evoked.catalogue import SPATIAL_KEYS, SpatialSettings
from ema.evoked.presets import LIBRARY as PROTOCOLS
from ema.evoked.presets import paired_pulse
from ema.evoked.spatial import DECAY_KEYS, FOOTPRINT_KEYS, RELEASE_KEYS, UNEVENNESS_KEYS
from ema.kept_results import why_not_measured
from ema.roi_selection import RoiSettings
from ema.spontaneous.detector import Detector, DetectorError
from ema.spontaneous.presets import LIBRARY as DETECTORS
from ema.spontaneous.presets import standard_detector
from ema.spontaneous.settings import GROUPS, DetectorSettings

EMA = Path(__file__).resolve().parent.parent / "ema"
GUI_FREE = ["definitions.py", "kept_results.py", "library.py", "labels.py", "excel.py", "recordings.py", "paths.py",
            "evoked", "spontaneous", "roi_selection/detection.py", "roi_selection/selections.py", "roi_selection/settings.py"]


def test_the_logic_never_imports_the_gui():
    """The measuring can be used from a script, and in worker processes, without Qt or matplotlib."""
    for name in GUI_FREE:
        for path in [EMA / name] if name.endswith(".py") else (EMA / name).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    assert not any(m.startswith(("PyQt5", "matplotlib")) for m in modules), f"{path} imports {modules}"


def test_every_spatial_measure_is_made_by_one_step():
    steps = [FOOTPRINT_KEYS, UNEVENNESS_KEYS, RELEASE_KEYS, DECAY_KEYS]
    assert sorted(key for step in steps for key in step) == sorted(SPATIAL_KEYS)


@pytest.mark.parametrize("settings_class", [RoiSettings, SpatialSettings, DetectorSettings])
def test_every_setting_can_be_shown_and_saved(settings_class):
    for f in fields(settings_class):
        details = f.metadata
        assert details["label"] and details["help"].endswith((".", "…")) and details["kind"] in KINDS, f.name
    defaults = settings_class()
    assert settings_class.from_dict(json.loads(json.dumps(defaults.to_dict()))) == defaults


def test_every_detector_setting_is_in_a_section():
    assert {f.metadata["group"] for f in fields(DetectorSettings)} <= set(GROUPS)


def test_a_setting_of_the_wrong_kind_is_refused():
    with pytest.raises(ValueError, match="Event threshold"):
        DetectorSettings.from_dict({"event_z": "eight"})
    assert DetectorSettings.from_dict({"event_z": 6}).event_z == 6.0
    assert issubclass(DetectorSettings, Settings)


def test_detector_files_of_earlier_names_still_open(tmp_path):
    data = standard_detector().to_dict()
    data["measures"]["per_event"] = ["z", "distance to the release centre"]
    data["measures"]["per_slice"] = ["share near the release centre"]
    detector = Detector.from_dict(data)
    assert detector.event_measures == ["strength", "distance to the ROI centre"]
    assert detector.slice_measures == ["share near the ROI centre"] and not detector.problems()


@pytest.mark.parametrize("content", [b"[]", b"{}", '{"format": "EMA spontaneous detector"}'.encode(),
                                     '{"name": "caf\xe9"}'.encode("cp1252"), b"not json"])
def test_a_damaged_file_in_the_library_is_left_out(tmp_path, content):
    for library, good in ((PROTOCOLS, paired_pulse()), (DETECTORS, standard_detector())):
        folder = tmp_path / library.noun
        folder.mkdir()
        (folder / "damaged.json").write_bytes(content)
        good.name = "Mine"
        library.in_folder(folder).save(good)
        names = [e.name for e in library.in_folder(folder).entries()]
        assert "Mine" in names and len(names) == len(library.entries()) + 1


def test_a_damaged_detector_says_so():
    with pytest.raises(DetectorError):
        Detector.from_dict({"format": "EMA spontaneous detector"})


def test_why_a_recording_was_not_measured_is_plain():
    assert why_not_measured(MemoryError()) == "There was not enough memory to measure it."
    assert why_not_measured(ValueError("It is not a movie.")) == "It is not a movie."
    assert why_not_measured(IndexError("index 5")).startswith("Unexpected error (please report it): IndexError")


def test_one_recording_that_fails_does_not_stop_the_evoked_run(tmp_path, monkeypatch, io_folder):
    from ema.evoked import analysis as evoked
    from ema.roi_selection import Selections, detect_folder
    from ema.roi_selection.selections import FolderSelection

    selections = Selections(io_folder.parents[2], RoiSettings())
    selections.folders[selections.name_of(io_folder)] = FolderSelection.from_detection(detect_folder(io_folder, RoiSettings()),
                                                                                        RoiSettings())
    real = evoked.measure

    def failing(protocol, trace, recording):
        if float(np.max(trace)) > 0 and not failing.done:
            failing.done = True
            raise IndexError("a bug")
        return real(protocol, trace, recording)

    failing.done = False
    monkeypatch.setattr(evoked, "measure", failing)
    analysis = evoked.Analysis(tmp_path)
    evoked.run(analysis, paired_pulse(corrected=False), selections)
    result = next(iter(analysis.folders.values()))
    assert len(result.recordings) == 2 and "IndexError: a bug" in result.skipped[-1][1]
