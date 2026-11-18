"""The Evoked Analysis Configurator window, driven without a screen."""

import numpy as np
import pytest
from matplotlib.backend_bases import MouseEvent
from PyQt5.QtWidgets import QApplication, QDoubleSpinBox, QFileDialog, QInputDialog, QMessageBox

from ema import user_settings
from ema.evoked.presets import LIBRARY
from ema.evoked.catalogue import KINETIC_KEYS
from ema.evoked.protocol import (
    AS_LISTED,
    DOUBLE,
    EVERY,
    LISTED,
    NO_PARTNER,
    PER_RECORDING,
    RATIO,
    RECORDED_AFTER,
    Protocol,
    Recording,
    Window,
)
from ema.evoked.template import LAST_PULSE, LIKE, Template
from ema.evoked_configurator.template_dialog import TemplateDialog
from ema.evoked_configurator.pulse_dialog import PlacePulsesDialog
from ema.evoked_configurator.widgets import FrameBox, Units
from ema.evoked_configurator.window import ConfiguratorWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def own_user_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "FILE", tmp_path / "user" / "settings.json")


@pytest.fixture
def window(app, tmp_path, io_folder):
    window = ConfiguratorWindow(user_folder=tmp_path / "protocols")
    window.use_example_folder(io_folder, None)
    window.resize(1400, 800)
    window.show()
    yield window
    window.bar.saved = window.protocol.to_dict()  # close without the unsaved-changes question
    window.close()


def answer(monkeypatch, name="text", reply=None, button=QMessageBox.Yes):
    """Answer the next name question with `reply`, and every yes/no question with `button`."""
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: (reply, reply is not None))
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: button)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: warnings.append(args[2]))
    return warnings


def drag(plot, start, end, height):
    """Drag on the plot from frame `start` to frame `end`, at a height given as a fraction of the plot."""
    plot.draw()
    for kind, frame in (("button_press_event", start), ("motion_notify_event", end), ("button_release_event", end)):
        x = plot.axes.transData.transform((frame, 0))[0]
        y = plot.axes.transAxes.transform((0, height))[1]
        plot.callbacks.process(kind, MouseEvent(kind, plot, x, y, 1))


# ---------------------------------------------------------------------------
# Opening and the example
# ---------------------------------------------------------------------------


def test_opens_on_the_first_built_in_protocol(window):
    assert window.protocol.name == "2P paired pulse" and window.bar.entry.built_in
    assert not window.bar.unsaved and not window.bar.buttons["Delete"].isEnabled()
    assert window.bar.box.count() == 3


def test_example_measures_the_stimulated_recordings(window):
    labels = [window.recording_box.itemText(i) for i in range(window.recording_box.count())]
    # each with the unstimulated recording made right after it; none was made after 200uA.tif and 300uA.tif: the one before
    assert labels == ["100uA.tif corrected with no1.tif", "200uA.tif corrected with no1.tif", "300uA.tif corrected with no1.tif"]
    values = window.measurement.values
    assert values["P1 response"] > 3 and np.isfinite(values["Tau"])
    # the synthetic recordings are short, so the example says P2 cannot be measured on them
    assert any("P2" in problem for problem in window.measurement.problems)
    assert "Example: P2" in window.problems.text()


def test_table_lists_every_measure_with_its_example_value(window):
    rows = {window.table.item(r, 0).text(): window.table.item(r, 1) for r in range(window.table.rowCount())}
    assert "P1 response" in rows and "PPR min" in rows and "Per recording" in rows
    assert float(rows["B1"].text()) == pytest.approx(window.measurement.values["B1"], rel=1e-3)
    assert rows["PPR min"].text() == ""  # slice values need every recording of a slice


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------


def test_editing_a_window_remeasures_and_marks_unsaved(window):
    before = window.measurement.values["B1"]
    window.protocol.baselines["B1"] = Window(60, 75)
    window.protocol_changed(False)
    assert window.bar.unsaved and "not saved" in window.bar.state.text()
    assert window.measurement.values["B1"] != before


def test_dragging_a_baseline_edge_and_a_peak_window(window):
    drag(window.plot, 93, 99, 0.2)  # the end of B1, in the lower half
    assert window.protocol.baselines["B1"] == Window(81, 99)
    drag(window.plot, 150, 160, 0.8)  # inside P1, in the upper half: moves it
    assert window.protocol.pulse("P1").peak == Window(93, 215)
    assert window.bar.unsaved


def test_dragging_a_stimulus(window):
    drag(window.plot, 103, 110, 0.5)
    assert window.protocol.pulse("P1").stimulus == 110


def test_renaming_a_pulse_follows_its_references(window):
    window.editors[1].rename("P1", "First")
    assert window.protocol.comparisons[0].relative_to == "First" and window.protocol.fits[0].after == "First"
    assert window.protocol.problems() == []


def test_switching_to_listed_recordings_and_back(window):
    editor = window.editors[0]
    editor.listed.setChecked(True)
    editor.add_recording()
    assert window.protocol.selection == LISTED and window.protocol.recordings[0].file == "hi1.tif"
    window.protocol.set_pulse_per_recording(window.protocol.pulse("P2"), True)
    window.protocol_changed(True)
    editor.every.setChecked(True)  # per-recording timing is not possible any more, so it is undone
    assert window.protocol.selection == EVERY and not window.protocol.pulse("P2").per_recording


def test_ratio_trace_needs_a_partner(window):
    editor = window.editors[0]
    editor.no_partner.setChecked(True)
    assert window.protocol.partner == NO_PARTNER and window.recording_box.itemText(0) == "100uA.tif"
    editor.ratio.setChecked(True)
    assert window.protocol.partner == RECORDED_AFTER and not editor.no_partner.isEnabled()
    assert window.recording_box.itemText(0) == "100uA.tif ÷ no1.tif" and window.protocol.problems() == []


def test_partners_as_listed_need_a_list(window):
    editor = window.editors[0]
    assert not editor.as_listed.isEnabled()
    editor.listed.setChecked(True)
    editor.as_listed.setChecked(True)
    editor.add_recording()
    assert window.protocol.recordings[0].unstimulated == "no2.tif"
    editor.every.setChecked(True)  # partners cannot be named any more: back to the time stamps
    assert window.protocol.partner == RECORDED_AFTER


def test_a_listed_partner_overrides_the_time_stamps(window):
    window.protocol.selection = LISTED
    window.protocol.recordings = [Recording("300uA.tif", "no7.tif"), Recording("200uA.tif")]
    window.protocol_changed(True)
    labels = [window.recording_box.itemText(i) for i in range(window.recording_box.count())]
    assert labels == ["300uA.tif  (no7.tif is not in this folder.)", "200uA.tif corrected with no1.tif"]


def test_the_correction_keeps_brightness_units(window):
    corrected = window.trace
    window.editors[0].no_partner.setChecked(True)
    raw = window.trace
    b1 = window.protocol.baselines["B1"]
    assert corrected[b1.start:b1.end].mean() == pytest.approx(raw[b1.start:b1.end].mean(), rel=0.01)
    assert not np.array_equal(corrected, raw)


def test_times_can_be_shown_in_ms(app):
    units = Units()
    units.in_ms = True
    box = FrameBox(units, 103)
    assert box.value() == pytest.approx(103 * 4.849, abs=0.05) and box.frames() == 103
    box.setValue(500.0)
    assert box.frames() == 103  # 500 ms is closest to frame 103
    optional = FrameBox(units, None, optional=True)
    assert optional.frames() is None and optional.text() == "none"


def test_place_pulses_dialog_starts_from_the_protocol(window):
    window.bar.open(2)  # 11P
    dialog = PlacePulsesDialog(window.protocol, window.units)
    first, count, interval, peak, baseline, shared = dialog.values()
    assert (first, count, peak, baseline, shared) == (103, 10, 19, 18, True)
    assert interval == pytest.approx((289 - 103) / 9, rel=1e-3)  # 10 Hz, from the whole train
    assert "10 pulse(s)" in dialog.summary.text()


# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------


def test_saving_a_built_in_protocol_asks_for_a_new_name(window, monkeypatch, tmp_path):
    answer(monkeypatch, reply="My 2P")
    window.protocol.baselines["B1"] = Window(70, 90)
    assert window.bar.save()
    assert (tmp_path / "protocols" / "My 2P.json").is_file()
    assert window.bar.entry.name == "My 2P" and not window.bar.entry.built_in and not window.bar.unsaved
    assert window.bar.buttons["Delete"].isEnabled() and window.bar.box.currentText() == "My 2P"
    assert Protocol.load(tmp_path / "protocols" / "My 2P.json").baselines["B1"] == Window(70, 90)
    assert LIBRARY.load(LIBRARY.entries()[0].path).baselines["B1"] == Window(81, 93)  # the built-in one is unchanged


def test_a_name_that_is_taken_is_asked_again(window, monkeypatch):
    replies = iter([("2P paired pulse", True), ("Another", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: next(replies))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    assert window.bar.save_as() and window.bar.entry.name == "Another"


def test_a_protocol_with_problems_is_not_saved(window, monkeypatch, tmp_path):
    warnings = answer(monkeypatch, reply="Broken")
    window.protocol.pulse("P1").baseline = "nothing"
    assert not window.bar.save()
    assert "Cannot save" not in warnings[-1] and "nothing" in warnings[-1]
    assert not (tmp_path / "protocols" / "Broken.json").exists()


def test_renaming_a_saved_protocol_replaces_its_file(window, monkeypatch, tmp_path):
    answer(monkeypatch, reply="First name")
    window.bar.save()
    window.protocol.name = "Second name"
    window.bar.save()
    assert [p.name for p in (tmp_path / "protocols").iterdir()] == ["Second name.json"]


def test_delete(window, monkeypatch, tmp_path):
    answer(monkeypatch, reply="Temporary")
    window.bar.save()
    window.bar.delete()
    assert not (tmp_path / "protocols" / "Temporary.json").exists()
    assert window.protocol.name == "2P paired pulse" and window.bar.box.count() == 3


def test_switching_protocol_asks_about_unsaved_changes(window, monkeypatch):
    window.protocol.baselines["B1"] = Window(70, 90)
    answer(monkeypatch, button=QMessageBox.Cancel)
    window.bar.choose(2)
    assert window.protocol.name == "2P paired pulse"
    answer(monkeypatch, button=QMessageBox.Discard)
    window.bar.choose(2)
    assert window.protocol.name == "11P pulse train"


def test_new_protocol_comes_from_the_template_form(window, monkeypatch):
    def fill_in(dialog):
        dialog.show_template(LIKE["11P pulse train"])
        dialog.name.setText("My train")
        dialog.count.setValue(5)
        return True

    monkeypatch.setattr(TemplateDialog, "exec_", fill_in)
    window.bar.new()
    protocol = window.protocol
    assert window.bar.entry is None and window.bar.unsaved and window.bar.box.currentText() == "My train  (not saved)"
    assert [p.name for p in protocol.pulses] == ["P1", "P2", "P3", "P4", "P5", "P6"]
    assert protocol.pulse("P6").per_recording and protocol.windows_follow_condition
    assert [r.condition for r in protocol.recordings] == [500, 1000, 2500, 5000]
    assert protocol.partner == AS_LISTED and protocol.recordings[0].unstimulated == "no2.tif"
    assert protocol.problems() == []


def test_template_form_fills_in_like_the_built_in_protocols(app):
    dialog = TemplateDialog()
    dialog.show_template(LIKE["2P paired pulse"])
    protocol = dialog.template().build()
    assert [p.stimulus for p in protocol.pulses] == [103, 928] and protocol.comparisons[0].name == "PPR"
    assert [f.name for f in protocol.fits] == ["Tau"] and protocol.selection == EVERY
    assert protocol.partner == RECORDED_AFTER and not dialog.unstimulated.isEnabled()
    dialog.partner_none.setChecked(True)
    assert dialog.template().build().partner == NO_PARTNER
    dialog.ratio.setChecked(True)  # a ratio needs a partner
    assert dialog.partner_after.isChecked() and not dialog.partner_none.isEnabled()
    dialog.show_template(LIKE["11P pulse train"])
    assert "Recovery pulse at frames 412 (500 ms)" in dialog.summary.text()
    dialog.delays.setText("500, x")
    assert "must be numbers" in dialog.summary.text()


def test_template_builds_both_shapes():
    paired = Template(pulses=2, interval_ms=4000, shared_baseline=False).build()
    assert list(paired.baselines) == ["B1", "B2"] and paired.pulse("P2").baseline == "B2"
    train = Template(pulses=10, interval_ms=100, shared_baseline=True, recovery=True, trace=RATIO, partner=AS_LISTED,
                     recovery_delays_ms=[500], recovery_after=LAST_PULSE).build()
    recording = train.recordings[0]
    last = 103 + round(9 * 100 / 4.849)
    assert recording.pulses["P11"].stimulus == last + round(500 / 4.849)
    assert (recording.file, recording.unstimulated) == ("hi1.tif", "no2.tif")
    assert train.fits == []  # a 10 Hz train has no room for a decay fit
    by_time = Template(pulses=10, interval_ms=100, recovery=True, trace=RATIO, recovery_delays_ms=[500]).build()
    assert by_time.partner == RECORDED_AFTER and by_time.recordings[0].unstimulated == ""


def test_changing_a_delay_moves_that_recordings_windows(window):
    window.bar.open(2)  # 11P: its recovery windows follow the delay
    recording = window.protocol.recordings[0]
    before = recording.pulses["P11"].peak
    window.protocol.set_condition(recording, 1000.0)  # 500 ms later: 103 frames
    shift = round(500 / 4.849)
    assert recording.pulses["P11"].peak == Window(before.start + shift, before.end + shift)
    assert recording.baselines["BLPre11"] == Window(401 + shift, 413 + shift)


def test_fits_are_drawn_and_can_be_dragged(window):
    frames = window.measurement.fit_frames["Tau"]
    labels = [a.get_text() for a in window.plot.overlays if hasattr(a, "get_text")]
    assert any(label.startswith(" Tau: τ = ") for label in labels)
    first, last = frames  # the synthetic recordings are short, so the fit ends at their last frame
    drag(window.plot, last, last - 100, 0.5)  # the end of the fit band, in the middle third
    assert window.protocol.fits[0].length == last - 100 - first
    drag(window.plot, first, first + 10, 0.5)  # its start: 10 more frames after the maximum
    assert window.protocol.fits[0].start == 14 and window.protocol.fits[0].length == last - 100 - first - 10


def test_kinetics_tab_chooses_measures_and_pulses(window):
    kinetics = window.editors[2]
    kinetics.checklist.set_chosen(["time to peak", "half-width"], notify=True)
    kinetics.pulses.boxes["P2"].setChecked(False)
    assert window.protocol.kinetic_measures == ["time to peak", "half-width"] and window.protocol.kinetic_pulses == ["P1"]
    names = [window.table.item(r, 0).text() for r in range(window.table.rowCount())]
    assert "P1 time to peak" in names and "P2 time to peak" not in names
    kinetics.checklist.set_chosen(KINETIC_KEYS, notify=True)
    assert window.protocol.kinetic_measures == KINETIC_KEYS


def test_double_fit_from_the_kinetics_tab(window):
    window.protocol.fits[0].kind = DOUBLE
    window.protocol_changed(True)
    names = [m.name for m in window.protocol.measures()]
    assert "Tau fast" in names and "Tau slow" in names and "Tau" not in names


def test_spatial_tab_shows_the_maps_and_measures(window):
    window.protocol.spatial_measures = ["footprint width", "centroid offset"]
    window.tabs.setCurrentIndex(3)
    assert window.views.currentIndex() == 1  # the map view replaces the trace
    assert window.spatial is not None and "P1" in window.spatial.maps
    rows = {window.table.item(r, 0).text(): window.table.item(r, 1).text()
            for r in range(window.table.rowCount()) if window.table.item(r, 1) is not None}
    assert rows["P1 footprint width"] not in ("", "–")
    window.tabs.setCurrentIndex(0)
    assert window.views.currentIndex() == 0


def test_spatial_tab_survives_switching_protocols(window):
    # once failed with "'NoneType' object has no attribute 'get_position'" and a KeyError on the colour bar
    window.protocol.spatial_measures = ["footprint width"]
    window.tabs.setCurrentIndex(3)
    for step in (lambda: window.bar.choose(2), lambda: window.tabs.setCurrentIndex(0),
                 lambda: window.tabs.setCurrentIndex(3), lambda: window.bar.choose(0)):
        window.bar.saved = window.protocol.to_dict()  # nothing unsaved to ask about
        step()
        window.plot.draw()
        window.spatial_view.canvas.draw()


def test_spatial_settings_are_edited_in_place(window):
    spatial = window.editors[3]
    spatial.inputs["region_um"].setValue(320.0)
    spatial.inputs["exclude_electrode"].setChecked(False)
    assert window.protocol.spatial.region_um == 320.0 and not window.protocol.spatial.exclude_electrode
    spatial.near_to_far.boxes["PPR"].setChecked(True)
    assert window.protocol.near_to_far == ["PPR"] and "PPR near-to-far" in [m.name for m in window.protocol.measures()]


def test_export_and_import(window, monkeypatch, tmp_path):
    exported = tmp_path / "shared" / "exported.json"
    exported.parent.mkdir()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(exported), ""))
    window.bar.export()
    assert Protocol.load(exported).name == "2P paired pulse"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(exported), ""))
    answer(monkeypatch, reply="2P from a colleague")  # the name is taken by the built-in one
    window.bar.import_file()
    assert window.bar.entry.name == "2P from a colleague" and (tmp_path / "protocols" / "2P from a colleague.json").is_file()


def test_per_recording_pulse_is_drawn_and_dragged_for_the_example_recording(window, train_folder, monkeypatch):
    protocol = window.protocol
    protocol.selection = LISTED
    protocol.recordings = []
    window.editors[0].add_recording()  # hi1.tif, corrected with no1.tif (made after it)
    protocol.set_baseline_per_recording("B2", True)
    protocol.set_pulse_per_recording(protocol.pulse("P2"), True)
    recording = protocol.recordings[0]
    recording.baselines["B2"], recording.pulses["P2"].peak = Window(200, 210), Window(210, 260)
    window.use_example_folder(train_folder, None)
    assert window.recording_box.currentText() == "hi1.tif corrected with no1.tif" and protocol.baselines["B2"] == PER_RECORDING
    drag(window.plot, 260, 280, 0.8)  # the end of P2's peak window, in this recording only
    assert recording.pulses["P2"].peak == Window(210, 280)


def test_decay_with_distance_is_shown_on_the_spatial_tab(window):
    window.protocol.spatial_measures = ["far-near decay ratio"]
    window.tabs.setCurrentIndex(3)
    window.spatial_view.view_box.setCurrentText("Decay with distance")
    assert "P1" in window.spatial.decays
    assert window.spatial_view.profile_axes.get_title() == "Decay near and far from the centre"
    rows = {window.table.item(r, 0).text() for r in range(window.table.rowCount())}
    assert "P1 far-near decay ratio" in rows


def test_fits_across_conditions_from_the_last_tab(window):
    window.bar.open(2)  # 11P: a recovery pulse set per recording
    editor = window.editors[4]
    editor.add_condition_fit()
    fit = window.protocol.condition_fits[0]
    assert (fit.name, fit.measure, fit.model, fit.plateau) == ("Recovery", "P11/P1", "recovery", 100.0)
    names = [m.name for m in window.protocol.measures() if m.per == "slice"]
    assert names[-2:] == ["Recovery time constant", "Recovery start"] and window.protocol.problems() == []
    window.editors[1].rename("P1", "First")  # the fit follows the comparison it uses
    window.editors[4].rename("P11/P1", "Recovered")
    assert window.protocol.condition_fits[0].measure == "Recovered"
    window.bar.open(0)  # 2P: no pulse set per recording, so an input-output fit
    window.editors[4].add_condition_fit()
    assert window.protocol.condition_fits[0].model == "saturation"


def test_means_over_recordings_from_the_last_tab(window):
    window.bar.open(2)  # 11P: its recordings are listed, hi1.tif to hi4.tif
    editor = window.editors[4]
    cell = lambda column: editor.means.grid.itemAtPosition(1, column).widget()  # noqa: E731
    editor.add_mean()
    mean = window.protocol.summary_means[0]
    assert (mean.name, mean.by, mean.files) == ("hi", "files", ["hi*"]) and window.protocol.problems() == []
    assert "P1 response mean hi" in [m.name for m in window.protocol.measures() if m.per == "slice"]
    cell(2).setText("hi1, hi2")
    cell(2).editingFinished.emit()
    assert (mean.files, mean.name, cell(0).text()) == (["hi1", "hi2"], "hi1+hi2", "hi1+hi2")  # the name follows
    cell(0).setText("first two")
    cell(0).editingFinished.emit()
    cell(2).setText("hi3")
    cell(2).editingFinished.emit()
    assert (mean.files, mean.name) == (["hi3"], "first two")  # a name given by hand stays

    window.bar.open(0)  # 2P: a mean over 100 to 400 µA
    mean = window.protocol.summary_means[0]
    low, high = cell(2).findChildren(QDoubleSpinBox)
    high.setValue(300)
    assert (mean.low, mean.high, mean.name, cell(0).text()) == (100, 300, "100-300", "100-300")
    editor.add_mean()  # there is a range already: the next is by file name
    second = window.protocol.summary_means[1]
    assert (second.by, second.name) == ("files", "")
    assert any("needs at least one file name" in p for p in window.protocol.problems())
    combo = editor.means.grid.itemAtPosition(2, 1).widget()
    combo.setCurrentIndex(0)
    combo.activated.emit(0)
    assert (second.by, second.name) == ("condition", "100-400") and window.protocol.problems() == []


def test_the_peaks_are_written_only_when_ticked(window):
    shown = lambda: [window.table.item(r, 0).text() for r in range(window.table.rowCount())]  # noqa: E731
    assert not window.protocol.write_peaks and "P1 peak" not in shown() and "P1 response" in shown()
    window.editors[1].write_peaks.setChecked(True)
    assert window.protocol.write_peaks and "P1 peak" in shown() and "P1 peak mean 100-400" in shown()
    window.editors[4].add_condition_fit()  # a peak can be fitted across conditions whether it is written or not
    window.protocol.condition_fits[0].measure = "P1 peak"
    window.editors[1].write_peaks.setChecked(False)
    assert window.protocol.problems() == []


def test_exclusions_from_their_tab_and_tried_on_earlier_results(window, monkeypatch, tmp_path):
    from ema.evoked.analysis import Analysis
    from ema.kept_results import FolderResult, RecordingResult

    analysis = Analysis(tmp_path / "earlier", method=window.protocol.to_dict())
    for n, b1s in enumerate([[100, 99], [100, 98], [100, 97], [100, 99], [100, 60]], 1):
        result = FolderResult(f"LKI WT M1/CTRL/Slice {n}", str(tmp_path))
        result.recordings = [RecordingResult(f"{100 * k}uA.tif", {"B1": b1}, condition=100.0 * k)
                             for k, b1 in enumerate(b1s, 1)]
        analysis.folders[(tmp_path / result.name).as_posix()] = result
    (tmp_path / "earlier").mkdir()
    analysis.save()

    window.tabs.setCurrentIndex(5)
    editor = window.editors[5]
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path / "earlier"))
    editor.choose_results()
    assert editor.results_label.text() == "earlier: 5 slices."
    editor.add_exclusion()
    exclusion = window.protocol.exclusions[0]
    assert (exclusion.measure, exclusion.statistic, exclusion.test, exclusion.factor) == ("B1", "spread of largest",
                                                                                          "interquartile", 1.5)
    assert editor.results_label.text() == "earlier: 1 of 5 slices would be left out."
    assert editor.verdicts.item(0, 0).text() == "LKI WT M1/CTRL/Slice 5" and editor.verdicts.item(0, 4).text() == "yes"
    assert editor.verdicts.item(0, 2).text() == "40"

    k = next(box for box in editor.list.findChildren(QDoubleSpinBox) if box.prefix() == "k = ")
    k.setValue(30)  # a number changes the sentence and the trial without rebuilding the form
    assert editor.results_label.text() == "earlier: 0 of 5 slices would be left out." and exclusion.factor == 30
    assert k in editor.list.findChildren(QDoubleSpinBox)
    sentence = editor.sentences[id(exclusion)][0].text()
    assert sentence == ("Leaves out a slice when B1: (largest − smallest) ÷ largest × 100 over its recordings is below "
                        "Q1 − 30 × IQR or above Q3 + 30 × IQR of all slices (Q1 and Q3 are the quartiles, IQR = Q3 − Q1).")
    assert window.protocol.problems() == [] and window.protocol.to_dict()["exclusions"][0]["factor"] == 30

    window.bar.open(1)  # another protocol: its own exclusions (none), and the same results to try them on
    assert window.protocol.exclusions == [] and editor.results_label.text() == "earlier: 5 slices."
