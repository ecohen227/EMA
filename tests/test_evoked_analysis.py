"""The evoked analysis: measuring the folders of an ROI file, keeping the results, and the Excel files."""

import shutil

import numpy as np
import pytest
from openpyxl import load_workbook
from PyQt5.QtWidgets import QApplication, QMessageBox

from ema import user_settings
from ema.evoked import analysis as analysis_module
from ema.evoked.analysis import FILE_NAME, Analysis, plan, run
from ema.evoked.protocol import AS_LISTED, LISTED, RATIO, Comparison, Fit, Protocol, Pulse, Recording, Window
from ema.evoked.workbook import PER_RECORDING, PER_SLICE, TablesLocked, _sheet_names, write_workbooks
from ema.evoked_configurator.example import ExampleFolder
from ema.roi_selection import FolderSelection, RoiSettings, Selections, detect_folder

from conftest import make_recording

FOLDERS = {
    "LKI HET M5821/CTRL 2H/Slice 1/input output": 0.3,
    "LKI WT F5823/IFN 4H/Slice 1/input output": 0.5,
    "LKI WT F5823/IFN 4H/Slice 2/input output": 0.6,
}


def small_protocol(**changes):
    protocol = Protocol(
        "small", sampling_interval_ms=5.0, baselines={"B1": Window(80, 100)},
        pulses=[Pulse("P1", "B1", Window(100, 160), stimulus=104)], fits=[Fit("Tau", "P1", 2, 100)],
        kinetic_measures=["half-decay"], spatial_measures=["footprint width"], summary_statistics=["mean"],
    )
    for name, value in changes.items():
        setattr(protocol, name, value)
    return protocol


@pytest.fixture(scope="module")
def study_template(tmp_path_factory):
    root = tmp_path_factory.mktemp("study")
    for name, response in FOLDERS.items():
        folder = root / name
        folder.mkdir(parents=True)
        make_recording(folder / "100uA.tif", response / 2, seed=1, clock="10:00:00")
        make_recording(folder / "no1.tif", 0.0, seed=2, clock="10:01:00")
        make_recording(folder / "200uA.tif", response, seed=3, clock="10:02:00")
        make_recording(folder / "no2.tif", 0.0, seed=4, clock="10:03:00")
    make_recording(root / "LKI WT F5823/IFN 4H/Slice 2/input output" / "200uA red.tif", 0.0, seed=5, clock="10:04:00")
    return root


@pytest.fixture
def study(study_template, tmp_path):
    """A copy of the study that a test may change, with the ROI file of every folder."""
    root = tmp_path / "recordings"
    shutil.copytree(study_template, root)
    settings = RoiSettings()
    selections = Selections(root, settings)
    for name in FOLDERS:
        selections.folders[name] = FolderSelection.from_detection(detect_folder(root / name, settings), settings)
    return selections


@pytest.fixture(autouse=True)
def own_user_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "FILE", tmp_path / "user" / "settings.json")


def measured(selections, protocol, output):
    analysis = Analysis.open(output)
    run(analysis, protocol, selections)
    analysis.save()
    return analysis


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------


def test_every_folder_is_measured_like_in_the_configurator(study, tmp_path):
    protocol = small_protocol()
    analysis = measured(study, protocol, tmp_path / "out")
    assert len(analysis.folders) == 3
    result = analysis.folders[(study.recordings_folder / "LKI HET M5821/CTRL 2H/Slice 1/input output").as_posix()]
    assert [(r.file, r.partner, r.condition) for r in result.recordings] == [("100uA.tif", "no1.tif", 100.0), ("200uA.tif", "no2.tif", 200.0)]

    roi_file = tmp_path / "roi_selections.json"
    study.save(roi_file)
    example = ExampleFolder(study.recordings_folder / "LKI HET M5821/CTRL 2H/Slice 1/input output", roi_file)
    choice = example.choices(protocol)[1]
    from ema.evoked.measures import measure
    from ema.evoked.spatial import measure_spatial
    expected = measure(protocol, example.trace(protocol, choice))
    spatial = measure_spatial(protocol, example.movie(protocol, choice), example.center, example.electrode, expected)
    values = result.recordings[1].values
    for name, value in {**expected.values, **spatial.values}.items():
        assert values[name] == pytest.approx(value, nan_ok=True), name
    assert result.summary["P1 response mean"] == pytest.approx(np.mean([r.values["P1 response"] for r in result.recordings]))


def test_skip_words_and_flagged_recordings_are_left_out(study, tmp_path):
    study.folders["LKI WT F5823/IFN 4H/Slice 1/input output"].flagged_files = {"100uA.tif": "drift", "no2.tif": ""}
    analysis = measured(study, small_protocol(), tmp_path / "out")
    result = analysis.folders[(study.recordings_folder / "LKI WT F5823/IFN 4H/Slice 1/input output").as_posix()]
    assert result.skipped == [["100uA.tif", "Flagged in ROI Selection: drift"], ["no2.tif", "Flagged in ROI Selection."]]
    assert [(r.file, r.partner) for r in result.recordings] == [("200uA.tif", "no1.tif")]  # no2 is flagged: the one before
    assert result.recordings[0].problems == ["No unstimulated recording was made after it, so it is paired with no1.tif, "
                                             "made 1 min before it."]
    other = analysis.folders[(study.recordings_folder / "LKI WT F5823/IFN 4H/Slice 2/input output").as_posix()]
    assert [r.file for r in other.recordings] == ["100uA.tif", "200uA.tif"]  # '200uA red' has a skip word


def test_a_listed_recording_that_is_missing_or_flagged_is_noted(study, tmp_path):
    protocol = small_protocol(trace=RATIO, partner=AS_LISTED, selection=LISTED, spatial_measures=[],
                              recordings=[Recording("200uA.tif", "no2.tif", 1.0), Recording("hi1.tif", "no1.tif", 2.0)])
    study.folders["LKI WT F5823/IFN 4H/Slice 1/input output"].flagged_files = {"no2.tif": ""}
    analysis = measured(study, protocol, tmp_path / "out")
    flagged = analysis.folders[(study.recordings_folder / "LKI WT F5823/IFN 4H/Slice 1/input output").as_posix()]
    assert flagged.skipped == [["no2.tif", "Flagged in ROI Selection."],
                               ["200uA.tif", "Its unstimulated partner no2.tif is flagged in ROI Selection."],
                               ["hi1.tif", "Not in this folder."]]
    assert not flagged.recordings and not flagged.summary


def test_a_rerun_with_nothing_changed_reads_nothing(study, tmp_path, monkeypatch):
    protocol = small_protocol()
    first = measured(study, protocol, tmp_path / "out")
    again = Analysis.open(tmp_path / "out")
    the_plan = plan(again, protocol, study)
    assert not the_plan.to_measure and len(the_plan.unchanged) == 3 and not the_plan.replace_all
    monkeypatch.setattr(analysis_module, "load_stack", lambda path: pytest.fail("a recording was read"))
    run(again, protocol, study, the_plan)
    assert again.folders.keys() == first.folders.keys()
    for key, result in first.folders.items():
        kept = again.folders[key]
        assert [r.values["P1 response"] for r in kept.recordings] == [r.values["P1 response"] for r in result.recordings]
        assert kept.summary == pytest.approx(result.summary)


def test_only_new_and_changed_folders_are_measured_again(study, tmp_path):
    protocol = small_protocol()
    measured(study, protocol, tmp_path / "out")
    root = study.recordings_folder
    make_recording(root / "LKI WT F5823/IFN 4H/Slice 1/input output" / "300uA.tif", 0.7, seed=9, clock="10:05:00")
    study.folders["LKI WT F5823/IFN 4H/Slice 2/input output"].roi_center = (40, 28)
    new = root / "LKI HET M5821/CTRL 2H/Slice 2/input output"
    shutil.copytree(root / "LKI HET M5821/CTRL 2H/Slice 1/input output", new)
    settings = RoiSettings()
    study.folders["LKI HET M5821/CTRL 2H/Slice 2/input output"] = FolderSelection.from_detection(detect_folder(new, settings), settings)

    analysis = Analysis.open(tmp_path / "out")
    the_plan = plan(analysis, protocol, study)
    assert sorted(study.name_of(folder) for folder, _, _ in the_plan.to_measure) == [
        "LKI HET M5821/CTRL 2H/Slice 2/input output",
        "LKI WT F5823/IFN 4H/Slice 1/input output",
        "LKI WT F5823/IFN 4H/Slice 2/input output",
    ]
    run(analysis, protocol, study, the_plan)
    assert len(analysis.folders) == 4
    assert [r.file for r in analysis.folders[(root / "LKI WT F5823/IFN 4H/Slice 1/input output").as_posix()].recordings] == [
        "100uA.tif", "200uA.tif", "300uA.tif"]


def test_folders_of_another_roi_file_are_kept(study, tmp_path):
    protocol = small_protocol()
    measured(study, protocol, tmp_path / "out")
    del study.folders["LKI HET M5821/CTRL 2H/Slice 1/input output"]
    analysis = Analysis.open(tmp_path / "out")
    the_plan = plan(analysis, protocol, study)
    assert len(the_plan.kept_others) == 1 and not the_plan.to_measure
    run(analysis, protocol, study, the_plan)
    assert len(analysis.folders) == 3
    run(analysis, protocol, study, the_plan, keep_others=False)
    assert len(analysis.folders) == 2


def test_another_protocol_measures_everything_again(study, tmp_path):
    measured(study, small_protocol(), tmp_path / "out")
    del study.folders["LKI HET M5821/CTRL 2H/Slice 1/input output"]
    changed = small_protocol(baselines={"B1": Window(70, 100)})
    analysis = Analysis.open(tmp_path / "out")
    the_plan = plan(analysis, changed, study)
    assert the_plan.replace_all and len(the_plan.to_measure) == 2 and len(the_plan.kept_others) == 1
    run(analysis, changed, study, the_plan)
    assert len(analysis.folders) == 2  # the folder that is not in the ROI file any more is dropped with the old results
    assert analysis.is_current(changed)


def test_a_stopped_run_keeps_what_was_measured(study, tmp_path):
    analysis = Analysis.open(tmp_path / "out")
    calls = []
    run(analysis, small_protocol(), study, cancelled=lambda: calls.append(1) or len(calls) > 2)
    assert len(analysis.folders) == 1  # the second folder was stopped half way, so it is measured next time
    assert len(plan(analysis, small_protocol(), study).to_measure) == 2


def test_the_analysis_file_is_read_back(study, tmp_path):
    analysis = measured(study, small_protocol(fits=[Fit("Tau", "P1", 2, 2)]), tmp_path / "out")  # too short: NaN
    again = Analysis.load(tmp_path / "out" / FILE_NAME)
    assert again.labels == analysis.labels and again.group_by == analysis.group_by
    for key, result in analysis.folders.items():
        loaded = again.folders[key]
        assert loaded.fingerprint == result.fingerprint
        for a, b in zip(result.recordings, loaded.recordings):
            assert b.values == pytest.approx(a.values, nan_ok=True)
            assert np.isnan(b.values["Tau"])


def test_the_condition_comes_from_the_list_or_the_file_name():
    protocol = small_protocol()
    assert protocol.condition_of("300uA.tif") == 300.0
    assert protocol.condition_of("12.5 ms.tif") == 12.5
    assert protocol.condition_of("hi1.tif") is None
    assert protocol.condition_of("hi1.tif", Recording("hi1.tif", condition=500.0)) == 500.0


# ---------------------------------------------------------------------------
# The Excel files
# ---------------------------------------------------------------------------


def rows(sheet):
    return [list(row) for row in sheet.iter_rows(values_only=True)]


def test_the_per_recording_file_has_a_table_and_a_prism_sheet_per_measure(study, tmp_path):
    protocol = small_protocol(comparisons=[Comparison("P1/P1", "P1", "P1")])
    analysis = measured(study, protocol, tmp_path / "out")
    write_workbooks(analysis)
    book = load_workbook(tmp_path / "out" / PER_RECORDING)
    assert book.sheetnames == ["Recordings", "B1", "P1", "P1 response", "P1 half-decay", "P1 footprint width",
                               "P1÷P1", "Tau", "Notes", "About"]
    table = rows(book["Recordings"])
    assert table[0][:13] == ["Folder", "Recording", "Unstimulated partner", "Line", "Genotype", "Treatment", "Duration",
                             "Sex", "Animal", "Slice", "Current (µA)", "ROI reviewed", "B1 (counts)"]
    assert [row[4] for row in table[1:]] == ["WT"] * 4 + ["HET"] * 2  # WT first: the order of the values
    assert table[1][:2] == ["LKI WT F5823/IFN 4H/Slice 1/input output", "100uA.tif"]

    prism = rows(book["P1 response"])
    assert prism[2][:4] == [None, "WT IFN", None, "HET CTRL"]  # two subcolumns per group: the most slices in a group
    assert prism[3] == ["Current (µA)", "Animal 5823 Slice 1", "Animal 5823 Slice 2", "Animal 5821 Slice 1", None]
    assert [row[0] for row in prism[4:]] == [100, 200]
    folder = analysis.folders[(study.recordings_folder / "LKI HET M5821/CTRL 2H/Slice 1/input output").as_posix()]
    assert prism[5][3] == pytest.approx(folder.recordings[1].values["P1 response"])
    assert prism[5][4] is None  # the padding of the HET CTRL group
    assert rows(book["Notes"])[1] == ["Nothing to note: every recording was measured.", None, None]


def test_the_per_slice_file_as_column_and_as_grouped_table(study, tmp_path):
    analysis = measured(study, small_protocol(), tmp_path / "out")
    write_workbooks(analysis)
    book = load_workbook(tmp_path / "out" / PER_SLICE)
    assert book.sheetnames[0] == "Slices" and "P1 response mean" in book.sheetnames
    assert rows(book["Slices"])[0][:11] == ["Folder", "Line", "Genotype", "Treatment", "Duration", "Sex", "Animal",
                                            "Slice", "Recordings measured", "ROI reviewed", "B1 mean (counts)"]
    column = rows(book["P1 response mean"])
    assert column[2] == ["WT IFN", "HET CTRL"]
    assert column[4][1] is None and column[3][1] is not None

    analysis.group_by, analysis.slice_rows_by = ["Genotype"], "Treatment"
    write_workbooks(analysis)
    grouped = rows(load_workbook(tmp_path / "out" / PER_SLICE)["P1 response mean"])
    assert grouped[2] == [None, "WT", None, "HET", None]
    assert [row[0] for row in grouped[4:]] == ["CTRL", "IFN"]
    assert grouped[4][1] is None and grouped[4][3] is not None  # CTRL: no WT slice, one HET slice
    assert grouped[5][1] is not None and grouped[5][2] is not None  # IFN: two WT slices


def test_notes_say_what_was_skipped_and_which_labels_are_missing(study, tmp_path):
    study.folders["LKI WT F5823/IFN 4H/Slice 1/input output"].flagged_files = {"100uA.tif": "drift"}
    analysis = measured(study, small_protocol(), tmp_path / "out")
    analysis.group_by = ["Genotype", "Duration"]
    analysis.labels.label("Duration").values["4H"] = ["4 hours"]
    write_workbooks(analysis)
    book = load_workbook(tmp_path / "out" / PER_RECORDING)
    notes = rows(book["Notes"])[1:]
    assert ["LKI WT F5823/IFN 4H/Slice 1/input output", "100uA.tif", "Not measured: Flagged in ROI Selection: drift"] in notes
    assert ["LKI WT F5823/IFN 4H/Slice 1/input output", None, "No Duration in the folder names."] in notes
    assert rows(book["P1"])[2][1] == "WT (no Duration)"


def test_a_file_open_in_excel_is_reported(study, tmp_path, monkeypatch):
    analysis = measured(study, small_protocol(), tmp_path / "out")
    real_replace = analysis_module.os.replace

    def locked(source, target):
        if str(target).endswith(PER_RECORDING):
            raise PermissionError("in use")
        return real_replace(source, target)

    monkeypatch.setattr("ema.excel.os.replace", locked)
    with pytest.raises(TablesLocked, match="Close it in Excel"):
        write_workbooks(analysis)
    assert (tmp_path / "out" / PER_SLICE).is_file() and not (tmp_path / "out" / PER_RECORDING).exists()
    assert not list((tmp_path / "out").glob("*.tmp.xlsx"))


def test_sheet_names_follow_the_rules_of_excel():
    names = _sheet_names(["P2/P1", "a*b?c", "x" * 40, "x" * 40 + "y", "Notes"])
    assert names["P2/P1"] == "P2÷P1" and names["a*b?c"] == "a-b-c"
    assert len(names["x" * 40]) == 31 and names["x" * 40 + "y"].endswith("(2)") and len(names["x" * 40 + "y"]) == 31
    assert names["Notes"] == "Notes (2)"


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_window_runs_an_analysis_and_writes_the_tables(app, study, tmp_path, monkeypatch):
    from ema.evoked_analysis.window import AnalysisWindow

    roi_file = tmp_path / "roi" / "roi_selections.json"
    roi_file.parent.mkdir()
    study.save(roi_file)
    protocol_file = tmp_path / "small.json"
    small_protocol().save(protocol_file)
    window = AnalysisWindow(user_folder=tmp_path / "protocols")
    window.roi_input.path.setText(str(roi_file))
    window.load_roi_file()
    window.method_box.addItem("small", str(protocol_file))
    window.method_box.setCurrentIndex(window.method_box.count() - 1)
    window.choose_method()
    window.output.path.setText(str(tmp_path / "out"))
    window.output_changed()
    assert window.folders_table.rowCount() == 3
    assert window.folders_table.item(0, 2).text() == "HET"
    assert window.output_info.text() == "New: every folder will be measured."

    window.start()
    window.worker.wait()
    app.processEvents()
    assert "3 folders measured (6 recordings), 0 unchanged." in window.status.text()
    assert window.status.text().endswith("Tables written.")
    assert (tmp_path / "out" / PER_RECORDING).is_file() and (tmp_path / "out" / PER_SLICE).is_file()
    assert window.output_info.text() == "3 folders measured before: only new or changed folders will be measured."

    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    window.start()
    window.worker.wait()
    app.processEvents()
    assert window.status.text() == "Done in 0 min 0 s: 0 folders measured (0 recordings), 3 unchanged.\nTables written."
    window.close()


def test_a_near_miss_is_resolved_from_the_window(app, study, tmp_path):
    from ema.evoked_analysis.window import AnalysisWindow

    root = study.recordings_folder
    (root / "LKI HET M5821/CTRL 2H").rename(root / "LKI HET M5821/Contrl 2H")
    study.folders = {name.replace("CTRL 2H", "Contrl 2H"): s for name, s in study.folders.items()}
    roi_file = tmp_path / "roi_selections.json"
    study.save(roi_file)
    window = AnalysisWindow(user_folder=tmp_path / "protocols")
    window.roi_input.path.setText(str(roi_file))
    window.load_roi_file()
    assert window.near_misses.misses[0].word == "Contrl" and window.tabs.tabText(2) == "Near misses (1)"
    assert window.folders_table.item(0, 3).text() == ""  # Treatment not found yet
    window.near_misses.apply(window.near_misses.misses[0], ("Treatment", "CTRL"))
    assert window.tabs.tabText(2) == "Near misses"
    assert window.folders_table.item(0, 3).text() == "CTRL"
    assert "Contrl" in window.analysis.labels.label("Treatment").values["CTRL"]
    assert user_settings.remembered("folder_labels")["labels"][2]["values"]["CTRL"][-1] == "Contrl"
    window.close()


def test_the_window_asks_before_keeping_folders_of_another_roi_file(app, study, tmp_path, monkeypatch):
    from ema.evoked_analysis.window import AnalysisWindow

    measured(study, small_protocol(), tmp_path / "out")
    del study.folders["LKI HET M5821/CTRL 2H/Slice 1/input output"]
    roi_file = tmp_path / "roi_selections.json"
    study.save(roi_file)
    protocol_file = tmp_path / "small.json"
    small_protocol().save(protocol_file)
    window = AnalysisWindow(user_folder=tmp_path / "protocols")
    window.roi_input.path.setText(str(roi_file))
    window.load_roi_file()
    window.method_box.addItem("small", str(protocol_file))
    window.method_box.setCurrentIndex(window.method_box.count() - 1)
    window.choose_method()
    window.output.path.setText(str(tmp_path / "out"))
    window.output_changed()
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: asked.append(args[2]) or QMessageBox.No)
    window.start()
    window.worker.wait()
    app.processEvents()
    assert "not in this ROI file (or do not pass the folder filter): 1 folder, for example" in asked[0]
    assert len(Analysis.load(tmp_path / "out" / FILE_NAME).folders) == 2
    window.close()


def test_extra_recordings_stay_off_the_measure_sheets(study, tmp_path):
    folder = study.recordings_folder / "LKI HET M5821/CTRL 2H/Slice 1/input output"
    make_recording(folder / "200uA test pulse.tif", 0.05, seed=7, clock="09:58:00")
    make_recording(folder / "test stim.tif", 0.05, seed=8, clock="09:59:00")
    analysis = measured(study, small_protocol(), tmp_path / "out")
    write_workbooks(analysis)
    book = load_workbook(tmp_path / "out" / PER_RECORDING)
    assert len(rows(book["Recordings"])) == 1 + 8
    prism = rows(book["P1 response"])
    assert [row[0] for row in prism[4:]] == [100, 200]  # no row for 'test stim.tif', which has no condition
    result = analysis.folders[folder.as_posix()]
    plain = next(r for r in result.recordings if r.file == "200uA.tif")
    assert prism[5][3] == pytest.approx(plain.values["P1 response"])  # 200uA.tif, not '200uA test pulse.tif'
    notes = [row[1:] for row in rows(book["Notes"])[1:]]
    assert ["200uA test pulse.tif", "Has the same condition as 200uA.tif, so the measure sheets show 200uA.tif only "
            "(both are on the Recordings sheet). To use this one instead, flag 200uA.tif in ROI Selection."] in notes
    assert ["test stim.tif", "Has no condition (its name does not start with a number), so it is on the Recordings "
            "sheet only."] in notes
