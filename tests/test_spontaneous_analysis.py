"""The spontaneous-event analysis: searching the folders of an ROI file, keeping the results, and the Excel files."""

import numpy as np
import pytest
import tifffile
from openpyxl import load_workbook
from PyQt5.QtWidgets import QApplication

from ema import user_settings
from ema.roi_selection import FolderSelection, RoiSettings, Selections
from ema.spontaneous.analysis import AUTOMATIC, FILE_NAME, NONE, REVIEWED, Analysis, Recordings, plan, run
from ema.spontaneous.detector import detector_v5
from ema.spontaneous.workbook import PER_EVENT, PER_SLICE, write_workbooks

from test_spontaneous import EVENTS, movie

FOLDERS = ["LKI HET M5821/CTRL 2H/Slice 1/input output", "LKI WT F5823/IFN 4H/Slice 2/input output"]


def write(path, stack):
    tifffile.imwrite(path, np.concatenate([stack[:1], stack]).clip(0, 65535).astype(np.uint16))  # EMA drops frame 0


@pytest.fixture(scope="module")
def study_files(tmp_path_factory):
    root = tmp_path_factory.mktemp("study")
    for n, name in enumerate(FOLDERS):
        folder = root / name
        folder.mkdir(parents=True)
        write(folder / "no1.tif", movie(seed=10 * n))  # two events
        write(folder / "no2.tif", movie(events=EVENTS[:1], seed=10 * n + 1))  # one event
        write(folder / "no3 red.tif", movie(seed=10 * n + 2))  # a skip word: not searched
        write(folder / "100uA.tif", movie(seed=10 * n + 3))  # stimulated: not searched
    return root


@pytest.fixture
def study(study_files):
    selections = Selections(study_files, RoiSettings())
    for name in FOLDERS:
        selections.folders[name] = FolderSelection((96, 96), (48, 48), 20, np.zeros((96, 96), bool), reviewed=True)
    return selections


@pytest.fixture(autouse=True)
def own_user_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "FILE", tmp_path / "user" / "settings.json")


def searched(study, output, detector=None, roi_file=True, **options):
    """Search the study's recordings folder, with its ROI file's selections or without."""
    analysis = Analysis.open(output)
    run(analysis, detector or detector_v5(), Recordings(study.recordings_folder, study if roi_file else None), workers=1,
        **options)
    analysis.save()
    return analysis


def test_every_unstimulated_recording_is_searched(study, tmp_path):
    analysis = searched(study, tmp_path / "out")
    assert len(analysis.folders) == 2
    for result in analysis.folders.values():
        assert [r.file for r in result.recordings] == ["no1.tif", "no2.tif"]
        assert [r.values["events"] for r in result.recordings] == [2, 1]
        assert [len(r.events) for r in result.recordings] == [2, 1]
        assert result.recordings[0].events[0]["onset"] < result.recordings[0].events[1]["onset"]
        assert result.summary["events"] == 3 and result.summary["rate"] > 0
        assert result.source == REVIEWED and not result.notes


def test_without_an_roi_file_the_electrode_and_centre_are_found_automatically(study, tmp_path):
    analysis = searched(study, tmp_path / "out", roi_file=False)
    assert len(analysis.folders) == 2
    for result in analysis.folders.values():
        assert result.source == AUTOMATIC and "found automatically" in result.notes[0]
        assert [r.values["events"] for r in result.recordings] == [2, 1]
        assert np.isfinite(result.recordings[0].events[0]["distance to the release centre"])


def test_a_folder_without_stimulated_recordings_has_no_electrode_and_no_centre(study_files, tmp_path):
    folder = tmp_path / "only unstimulated" / "Slice 9"
    folder.mkdir(parents=True)
    write(folder / "no1.tif", movie(seed=99))
    analysis = Analysis.open(tmp_path / "out")
    run(analysis, detector_v5(), Recordings(tmp_path / "only unstimulated"), workers=1)
    result = next(iter(analysis.folders.values()))
    assert result.source == NONE and result.recordings[0].values["events"] == 2
    assert np.isnan(result.recordings[0].events[0]["distance to the release centre"])
    assert np.isnan(result.summary["share near the release centre"])


def test_an_roi_file_of_another_recordings_folder_is_not_used(study, tmp_path):
    other = Selections(tmp_path / "elsewhere", RoiSettings())
    assert Recordings(study.recordings_folder, other).selections is None


def test_recordings_are_searched_in_parallel_with_the_same_results(study, tmp_path):
    one = searched(study, tmp_path / "one")
    analysis = Analysis.open(tmp_path / "two")
    run(analysis, detector_v5(), Recordings(study.recordings_folder, study), workers=2)
    for key, result in one.folders.items():
        other = analysis.folders[key]
        assert [r.values["events"] for r in other.recordings] == [r.values["events"] for r in result.recordings]
        assert other.recordings[0].events[0]["z"] == pytest.approx(result.recordings[0].events[0]["z"])


def test_flagged_recordings_are_not_searched(study, tmp_path):
    study.folders[FOLDERS[0]].flagged_files = {"no2.tif": "bubble"}
    analysis = searched(study, tmp_path / "out")
    result = analysis.folders[(study.recordings_folder / FOLDERS[0]).as_posix()]
    assert [r.file for r in result.recordings] == ["no1.tif"]
    assert result.skipped == [["no2.tif", "Flagged in ROI Selection: bubble"]]


def test_a_rerun_searches_only_what_changed(study, tmp_path, monkeypatch):
    detector = detector_v5()
    searched(study, tmp_path / "out", detector)
    analysis = Analysis.open(tmp_path / "out")
    recordings = Recordings(study.recordings_folder, study)
    assert not plan(analysis, detector, recordings).to_measure
    detector.event_measures = ["z"]  # other measures in the tables: no new search
    assert analysis.is_current(detector) and not plan(analysis, detector, recordings).to_measure
    study.folders[FOLDERS[0]].roi_center = (40, 40)  # a changed ROI file entry: that folder again
    assert len(plan(analysis, detector, Recordings(study.recordings_folder, study)).to_measure) == 1
    detector.settings.event_z = 9.0  # other settings: everything again
    the_plan = plan(analysis, detector, recordings)
    assert the_plan.replace_all and len(the_plan.to_measure) == 2


def test_a_stopped_run_keeps_the_finished_folders(study, tmp_path):
    calls = []
    analysis = searched(study, tmp_path / "out", cancelled=lambda: calls.append(1) or len(calls) > 2)
    assert len(analysis.folders) == 1
    assert len(plan(analysis, detector_v5(), Recordings(study.recordings_folder, study)).to_measure) == 1


def test_the_analysis_file_is_read_back(study, tmp_path):
    analysis = searched(study, tmp_path / "out")
    again = Analysis.load(tmp_path / "out" / FILE_NAME)
    for key, result in analysis.folders.items():
        loaded = again.folders[key]
        assert loaded.summary == pytest.approx(result.summary, nan_ok=True)
        assert loaded.recordings[0].events[0] == pytest.approx(result.recordings[0].events[0], nan_ok=True)


def rows(sheet):
    return [list(row) for row in sheet.iter_rows(values_only=True)]


def test_the_two_excel_files(study, tmp_path):
    detector = detector_v5()
    analysis = searched(study, tmp_path / "out", detector)
    write_workbooks(analysis)
    events = load_workbook(tmp_path / "out" / PER_EVENT)
    assert events.sheetnames[:2] == ["Events", "Recordings"] and events.sheetnames[-2:] == ["Notes", "About"]
    assert "width" in events.sheetnames and "fitted peak" in events.sheetnames
    table = rows(events["Events"])
    assert table[0][:10] == ["Folder", "Recording", "Line", "Genotype", "Treatment", "Duration", "Sex", "Animal", "Slice", "Event"]
    assert len(table) == 1 + 6 and [row[1] for row in table[1:4]] == ["no1.tif", "no1.tif", "no2.tif"]
    assert [row[3] for row in table[1:]] == ["WT"] * 3 + ["HET"] * 3
    prism = rows(events["width"])
    assert prism[2] == ["WT IFN", "HET CTRL"] and sum(v is not None for v in prism[3]) == 2 and len(prism) == 3 + 3
    recordings = rows(events["Recordings"])
    assert recordings[0][:11] == ["Folder", "Recording", "Line", "Genotype", "Treatment", "Duration", "Sex", "Animal", "Slice",
                                  "Electrode and centre", "events"]
    assert recordings[1][9] == REVIEWED

    slices_book = load_workbook(tmp_path / "out" / PER_SLICE)
    slices = rows(slices_book["Slices"])
    assert "width median (µm)" in slices[0] and "rate (per min)" in slices[0]
    width = slices[0].index("width median (µm)")
    assert slices[1][width] == pytest.approx(np.median([e["width"] for _, e in
                                                        analysis.folders[(study.recordings_folder / FOLDERS[1]).as_posix()].events()]))
    assert rows(slices_book["rate"])[2] == ["WT IFN", "HET CTRL"]
    analysis.group_by, analysis.slice_rows_by = ["Genotype"], "Treatment"
    write_workbooks(analysis)
    grouped = rows(load_workbook(tmp_path / "out" / PER_SLICE)["rate"])
    assert grouped[2] == [None, "WT", "HET"] and [row[0] for row in grouped[4:]] == ["CTRL", "IFN"]


def test_measures_not_chosen_stay_out_of_the_tables(study, tmp_path):
    detector = detector_v5()
    detector.event_measures, detector.slice_event_measures, detector.slice_measures = ["z"], [], ["rate"]
    analysis = searched(study, tmp_path / "out", detector)
    write_workbooks(analysis)
    assert load_workbook(tmp_path / "out" / PER_EVENT).sheetnames == ["Events", "Recordings", "z", "Notes", "About"]
    assert load_workbook(tmp_path / "out" / PER_SLICE).sheetnames == ["Slices", "rate", "Notes", "About"]


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_window_searches_and_writes_the_tables(app, study, tmp_path):
    from ema.spontaneous_analysis.window import SpontaneousAnalysisWindow

    roi_file = tmp_path / "roi" / "roi_selections.json"
    roi_file.parent.mkdir()
    study.save(roi_file)
    window = SpontaneousAnalysisWindow(user_folder=tmp_path / "detectors", workers=1)
    assert window.windowTitle() == "EMA – Spontaneous Event Analysis" and window.method_box.currentText() == "Detector v5  (built in)"
    assert window.problems()[0] == "Choose a recordings folder."
    window.recordings_input.path.setText(str(study.recordings_folder))
    window.load_recordings_folder()
    assert window.folders_table.rowCount() == 2
    assert window.recordings_info.text() == "2 of 2 folders will be searched."
    assert window.roi_info.text().startswith("None: ")
    window.roi_input.path.setText(str(roi_file))
    window.load_roi_file()
    assert window.roi_info.text() == "It covers every one of these folders."
    window.output.path.setText(str(tmp_path / "out"))
    window.output_changed()
    window.start()
    window.worker.wait()
    app.processEvents()
    assert "2 folders measured (4 recordings), 0 unchanged." in window.status.text()
    assert (tmp_path / "out" / PER_EVENT).is_file() and (tmp_path / "out" / PER_SLICE).is_file()
    assert window.output_info.text() == "2 folders measured before: only new or changed folders will be measured."
    window.close()
