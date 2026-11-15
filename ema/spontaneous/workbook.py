"""The two Excel files of a spontaneous-event analysis, laid out to paste into Prism.

Spontaneous per event.xlsx
    *Events*: one row per event: its folder and recording, the labels of its
    folder, and every chosen per-event measure. *Recordings*: one row per
    searched recording, with every chosen per-recording measure. Then one
    sheet per event measure, laid out as a Prism column table: one column
    per group, every event of the group's slices below (for distributions).

Spontaneous per slice.xlsx
    *Slices*: one row per slice (recording folder): its labels and every
    chosen per-slice measure. Then one sheet per measure: a Prism column
    table (one column per group, one value per slice), or, when the rows are
    set to a label, a grouped table with one row per value of that label.

Both end with *Notes* (what was not searched and why, labels to check) and
*About* (the detector, the labels, and what every measure is).
"""

from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment

from .. import __version__
from ..excel import (
    BOLD,
    bold_rows,
    cell,
    column_table,
    finish_table,
    grouped_table,
    groups,
    heading,
    label_lines,
    notes_sheet,
    save_workbooks,
    sheet_names,
    slices,
)
from .measures import EVENT, RECORDING, SLICE, summarise_events

PER_EVENT = "Spontaneous per event.xlsx"
PER_SLICE = "Spontaneous per slice.xlsx"


def write_workbooks(analysis):
    """Write both files into the analysis's output folder. Returns their paths (TablesLocked if one is open in Excel)."""
    detector = analysis.detector_object()
    found = slices(analysis)
    books = {PER_EVENT: _per_event(analysis, detector, found), PER_SLICE: _per_slice(analysis, detector, found)}
    return save_workbooks(analysis.folder, books)


def slice_values(detector, result):
    """Every per-slice measure of a slice: the kept ones and the summaries of its events' measures."""
    events = [event for _, event in result.events()]
    return {**result.summary, **summarise_events(events, detector.slice_event_measures, detector.slice_statistics)}


def slice_measures(detector):
    """(name, unit, explanation) of every chosen per-slice measure, in order."""
    units = {m.key: m for m in SLICE}
    event_units = {m.key: m for m in EVENT}
    chosen = [(units[k].key, "" if units[k].unit == "count" else units[k].unit, units[k].explanation)
              for k in [m.key for m in SLICE] if k in detector.slice_measures]
    for key in detector.slice_event_measures:
        for statistic in detector.slice_statistics:
            chosen.append((f"{key} {statistic}", event_units[key].unit, f"The {statistic} of the slice's events' {key}."))
    return chosen


def _per_event(analysis, detector, found):
    workbook = Workbook()
    label_names = analysis.labels.names()
    event_measures = [m for m in EVENT if m.key in detector.event_measures]
    recording_measures = [m for m in RECORDING if m.key in detector.recording_measures]

    sheet = workbook.active
    sheet.title = "Events"
    header = ["Folder", "Recording", *label_names, "Event"]
    sheet.append(header + [heading(m.key, m.unit) for m in event_measures])
    for item in found:
        for recording in item.result.recordings:
            for n, event in enumerate(recording.events, start=1):
                row = [item.result.name, recording.file, *[item.labels[name] for name in label_names], n]
                sheet.append(row + [cell(event.get(m.key)) for m in event_measures])
    finish_table(sheet, 2)
    if sheet.max_row == 1:
        sheet.append(["No event was found."])

    sheet = workbook.create_sheet("Recordings")
    header = ["Folder", "Recording", *label_names, "Electrode and centre"]
    sheet.append(header + [heading(m.key, "" if m.unit == "count" else m.unit) for m in recording_measures])
    for item in found:
        for recording in item.result.recordings:
            row = [item.result.name, recording.file, *[item.labels[name] for name in label_names], item.result.source]
            sheet.append(row + [cell(recording.values.get(m.key)) for m in recording_measures])
    finish_table(sheet, 2)

    names = sheet_names(m.key for m in event_measures)
    by_group = groups(analysis, found)
    for measure in event_measures:
        columns = {group: [e.get(measure.key) for item in members for _, e in item.result.events()]
                   for group, members in by_group.items()}
        column_table(workbook.create_sheet(names[measure.key]), heading(measure.key, measure.unit), columns)

    notes_sheet(workbook, _notes(found), "Nothing to note: every recording was searched.")
    _about_sheet(workbook, analysis, detector, [(m.key, m.unit, m.explanation) for m in event_measures + recording_measures])
    return workbook


def _per_slice(analysis, detector, found):
    workbook = Workbook()
    label_names = analysis.labels.names()
    measures = slice_measures(detector)
    values = {item.key: slice_values(detector, item.result) for item in found}

    sheet = workbook.active
    sheet.title = "Slices"
    header = ["Folder", *label_names, "Recordings searched", "Electrode and centre"]
    sheet.append(header + [heading(name, unit) for name, unit, _ in measures])
    for item in found:
        row = [item.result.name, *[item.labels[name] for name in label_names], len(item.result.recordings),
               item.result.source]
        sheet.append(row + [cell(values[item.key].get(name)) for name, _, _ in measures])
    finish_table(sheet, 1)

    names = sheet_names(name for name, _, _ in measures)
    rows_label = analysis.labels.label(analysis.slice_rows_by) if analysis.slice_rows_by not in analysis.group_by else None
    by_group = groups(analysis, found)
    for name, unit, _ in measures:
        sheet = workbook.create_sheet(names[name])
        if rows_label is None:
            columns = {group: [values[m.key].get(name) for m in members] for group, members in by_group.items()}
            column_table(sheet, heading(name, unit), columns)
        else:
            pairs = {group: [(m.labels[rows_label.name], values[m.key].get(name)) for m in members]
                     for group, members in by_group.items()}
            grouped_table(sheet, heading(name, unit), rows_label, pairs)

    notes_sheet(workbook, _notes(found), "Nothing to note: every recording was searched.")
    _about_sheet(workbook, analysis, detector, measures)
    return workbook


def _notes(found):
    notes = []
    for item in found:
        notes += [[item.result.name, "", note] for note in item.notes + item.result.notes]
        notes += [[item.result.name, file, f"Not searched: {why}"] for file, why in item.result.skipped]
    return notes


def _about_sheet(workbook, analysis, detector, measures):
    sheet = workbook.create_sheet("About")
    s = detector.settings
    lines = [
        ("Made by", f"EMA {__version__}, Spontaneous Event Analysis, on {datetime.now():%d %B %Y at %H:%M}"),
        ("Detector", detector.name),
        ("", detector.description),
        ("Searched", "The unstimulated recordings of each folder (named 'no' and a number)"
                     + (f", without those named with {', '.join(detector.skip_words)}" if detector.skip_words else "") + "."),
        ("Settings", f"Spatial filter σ {s.blur_um:g} µm; template rise {s.rise_ms:g} ms, decay {s.decay_ms:g} ms; events at "
                     f"z ≥ {s.event_z:g} (regions of z ≥ {s.region_z:g}); echo rule {'on' if s.echo_rule else 'off'}; end trim "
                     f"{s.end_trim_ms:g} ms. Every setting is in the detector's file."),
        ("Recordings", analysis.recordings_folder),
        ("ROI file", analysis.roi_file or "None: each folder's electrode and release centre were found automatically."),
        ("Electrode and centre", "Where each folder's electrode and release centre came from: 'ROI file, reviewed' or "
                                 "'ROI file' (its entry in the ROI file), 'automatic' (found from the folder's stimulated "
                                 "recordings, as in ROI Selection), or 'none' (no stimulated recording: no electrode, and "
                                 "the place measures are empty)."),
        ("Slices", f"{sum(bool(r.recordings) for r in analysis.folders.values())} recording folders, one slice each"),
        ("Groups", "Slices are grouped by " + (", ".join(analysis.group_by) if analysis.group_by else "nothing (one group)")),
        *label_lines(analysis.labels),
        ("Empty cells", "A measure that could not be measured is left empty, never 0."),
    ]
    for key, text in lines:
        sheet.append([key, text])
        sheet.cell(sheet.max_row, 1).font = BOLD
    sheet.append([])
    sheet.append(["Measure", "Unit", "What it is"])
    bold_rows(sheet, (sheet.max_row,))
    for name, unit, explanation in measures:
        sheet.append([name, unit, explanation])
    sheet.column_dimensions["A"].width = 30
    sheet.column_dimensions["B"].width = 16
    sheet.column_dimensions["C"].width = 110
    for row in sheet.iter_rows():
        for item in row:
            item.alignment = Alignment(wrap_text=True, vertical="top")
