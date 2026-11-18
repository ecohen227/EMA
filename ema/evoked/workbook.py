"""The two Excel files of an evoked analysis, laid out to paste into Prism.

Evoked per recording.xlsx
    *Recordings*: one row per recording: its folder, file and partner, the
    labels of its folder, its condition, and every per-recording measure.
    Then one sheet per measure, laid out as a Prism grouped table: one row
    per condition (such as each current), one group of columns per group of
    slices (such as WT CTRL), and in each group one column per slice.

Evoked per slice.xlsx
    *Slices*: one row per slice (recording folder): its labels and every
    per-slice measure. Then one sheet per measure, laid out as a Prism
    column table: one column per group, one value per slice; or, when the
    rows are set to a label, as a grouped table with one row per value of
    that label.

Both end with *Notes* (what was skipped or could not be measured, and why)
and *About* (the protocol, the labels, and what every measure is). When the
protocol has exclusions, the slices they leave out are in neither file, and
both have an *Exclusions* sheet with the value of every slice.
"""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment

from .. import __version__
from ..excel import (
    BOLD,
    bold_rows,
    cell,
    column_table,
    finish_table,
    group_name,
    grouped_table,
    groups,
    heading,
    label_lines,
    notes_sheet,
    save_workbooks,
    sheet_names,
    slices,
    write_title,
)
from .exclusions import judge, left_out

PER_RECORDING = "Evoked per recording.xlsx"
PER_SLICE = "Evoked per slice.xlsx"


def write_workbooks(analysis):
    """Write both files into the analysis's output folder (the per-slice file only if the protocol says so).
    Returns their paths.

    Raises TablesLocked if a file cannot be replaced (open in Excel); the
    other file is still written.
    """
    protocol = analysis.protocol()
    found = slices(analysis)
    verdicts = judge(protocol, found, lambda item: group_name(analysis, item.group))
    out = left_out(verdicts)
    kept = [item for item in found if item.key not in out]
    books = {PER_RECORDING: _per_recording(analysis, protocol, kept, verdicts)}
    if protocol.slice_file:
        books[PER_SLICE] = _per_slice(analysis, protocol, kept, verdicts)
    return save_workbooks(analysis.folder, books)


# ---------------------------------------------------------------------------
# The two files
# ---------------------------------------------------------------------------


def _per_recording(analysis, protocol, found, verdicts):
    workbook = Workbook()
    measures = [m for m in protocol.measures() if m.per == "recording"]
    label_names = analysis.labels.names()
    partner = ["Unstimulated partner"] if protocol.uses_partner else []

    sheet = workbook.active
    sheet.title = "Recordings"
    header = ["Folder", "Recording", *partner, *label_names, protocol.condition_label, "ROI reviewed"]
    sheet.append(header + [heading(m.name, m.unit) for m in measures])
    for item in found:
        for recording in _ordered(item.result.recordings):
            row = [item.result.name, recording.file] + ([recording.partner] if partner else [])
            row += [item.labels[name] for name in label_names]
            row += [recording.condition, "yes" if item.result.reviewed else "no"]
            sheet.append(row + [cell(recording.values.get(m.name)) for m in measures])
    finish_table(sheet, len(header))

    names = sheet_names(m.name for m in measures)
    by_group = groups(analysis, found)
    width = max((len(members) for members in by_group.values()), default=1)
    with_conditions = _with_conditions(found)
    rows = _condition_rows(found, with_conditions)
    by_row = {item.key: _by_row(item) for item in found}
    notes = [note for item in found for note in _row_notes(item, with_conditions)]
    for measure in measures:
        sheet = workbook.create_sheet(names[measure.name])
        write_title(sheet, heading(measure.name, measure.unit), f"Prism: Grouped table, {width} replicates side by side. "
                    "Copy from A5 to the last value; paste at the first row title.")
        top = ["" for _ in range(1 + width * len(by_group))]
        names_row = [protocol.condition_label] + [""] * (width * len(by_group))
        for g, (group, members) in enumerate(by_group.items()):
            top[1 + g * width] = group
            for s, member in enumerate(members):
                names_row[1 + g * width + s] = member.short_name
        sheet.append(top)
        sheet.append(names_row)
        for row_key in rows:
            line = [row_key]
            for members in by_group.values():
                recordings = [by_row[member.key].get(row_key) for member in members]
                values = [cell(r.values.get(measure.name)) if r is not None else None for r in recordings]
                line += values + [None] * (width - len(values))
            sheet.append(line)
        bold_rows(sheet, (3, 4))
        sheet.freeze_panes = "B5"

    notes += _notes(found, per_recording=True) + _exclusion_notes(verdicts)
    notes_sheet(workbook, notes)
    _exclusions_sheet(workbook, analysis, protocol, verdicts)
    _about_sheet(workbook, analysis, protocol, measures, verdicts)
    return workbook


def _per_slice(analysis, protocol, found, verdicts):
    workbook = Workbook()
    measures = [m for m in protocol.measures() if m.per == "slice"]
    label_names = analysis.labels.names()

    sheet = workbook.active
    sheet.title = "Slices"
    header = ["Folder", *label_names, "Recordings measured", "ROI reviewed"]
    sheet.append(header + [heading(m.name, m.unit) for m in measures])
    for item in found:
        row = [item.result.name] + [item.labels[name] for name in label_names]
        row += [len(item.result.recordings), "yes" if item.result.reviewed else "no"]
        sheet.append(row + [cell(item.result.summary.get(m.name)) for m in measures])
    finish_table(sheet, len(header))
    if not measures:
        sheet.append([])
        sheet.append(["The protocol has no per-slice measures. Choose them in the configurator, on the tab "
                      "Comparisons and summary."])

    names = sheet_names(m.name for m in measures)
    rows_label = analysis.labels.label(analysis.slice_rows_by) if analysis.slice_rows_by not in analysis.group_by else None
    by_group = groups(analysis, found)
    for measure in measures:
        sheet = workbook.create_sheet(names[measure.name])
        title = heading(measure.name, measure.unit)
        if rows_label is None:
            columns = {group: [m.result.summary.get(measure.name) for m in members] for group, members in by_group.items()}
            column_table(sheet, title, columns)
        else:
            pairs = {group: [(m.labels[rows_label.name], m.result.summary.get(measure.name)) for m in members]
                     for group, members in by_group.items()}
            grouped_table(sheet, title, rows_label, pairs)

    notes_sheet(workbook, _notes(found, per_recording=False) + _exclusion_notes(verdicts))
    _exclusions_sheet(workbook, analysis, protocol, verdicts)
    _about_sheet(workbook, analysis, protocol, measures, verdicts)
    return workbook


# ---------------------------------------------------------------------------
# Rows of the Prism sheets
# ---------------------------------------------------------------------------


def _row_key(recording):
    return recording.condition if recording.condition is not None else recording.file


def _ordered(recordings):
    """Recordings by condition (those without one after); with the same condition, the plainest name first.

    The plainest name is the shortest, so 200uA.tif comes before
    '200uA test pulse.tif' and 50uA.tif before '50uA (2).tif'.
    """
    return sorted(recordings, key=lambda r: (r.condition is None, r.condition or 0, len(Path(r.file).stem), r.file.lower()))


def _with_conditions(found):
    """True when any recording has a condition: the rows of the measure sheets are then the conditions only."""
    return any(r.condition is not None for s in found for r in s.result.recordings)


def _condition_rows(found, with_conditions):
    """The rows of the measure sheets: every condition of any slice, in order; file names when no recording has one."""
    if with_conditions:
        return sorted({r.condition for s in found for r in s.result.recordings if r.condition is not None})
    return sorted({r.file for s in found for r in s.result.recordings}, key=str.lower)


def _by_row(item):
    """{row: recording} of a slice; of recordings with the same condition, the plainest name."""
    found = {}
    for recording in _ordered(item.result.recordings):
        found.setdefault(_row_key(recording), recording)
    return found


def _row_notes(item, with_conditions):
    """Notes on the recordings of a slice that are not on the measure sheets."""
    notes, seen = [], {}
    for recording in _ordered(item.result.recordings):
        key = _row_key(recording)
        if with_conditions and recording.condition is None:
            notes.append([item.result.name, recording.file, "Has no condition (its name does not start with a number), so "
                          "it is on the Recordings sheet only."])
        elif key in seen:
            notes.append([item.result.name, recording.file, f"Has the same condition as {seen[key]}, so the measure sheets "
                          f"show {seen[key]} only (both are on the Recordings sheet). To use this one instead, flag "
                          f"{seen[key]} in ROI Selection."])
        else:
            seen[key] = recording.file
    return notes


# ---------------------------------------------------------------------------
# Notes and About
# ---------------------------------------------------------------------------


def _notes(found, per_recording):
    notes = []
    for item in found:
        notes += [[item.result.name, "", note] for note in item.notes]
        for file, why in item.result.skipped:
            notes.append([item.result.name, file, f"Not measured: {why}"])
        if per_recording:
            for recording in item.result.recordings:
                notes += [[item.result.name, recording.file, problem] for problem in recording.problems]
    return notes


def _exclusion_notes(verdicts):
    """A note for each slice an exclusion leaves out, or could not test."""
    return [[v.slice.result.name, "", v.why] for v in verdicts if v.why]


def _exclusions_sheet(workbook, analysis, protocol, verdicts):
    """The exclusions, then one row per slice and exclusion: its value, the limits, and whether it is left out."""
    if not protocol.exclusions:
        return
    sheet = workbook.create_sheet("Exclusions")
    count = len(left_out(verdicts))
    write_title(sheet, "Exclusions", f"{count} of {len({v.slice.key for v in verdicts})} slices are left out of both "
                                     "files (per recording and per slice). A slice is left out when any exclusion says so.")
    units = {m.name: m.unit for m in protocol.recording_measures()}
    for number, exclusion in enumerate(protocol.exclusions, 1):
        unit = exclusion.unit(units.get(exclusion.measure, ""))
        sheet.append([f"Exclusion {number}", f"{exclusion.value_text(protocol.condition_label)}; left out when "
                                             f"{exclusion.test_text(unit)}."])
        sheet.cell(sheet.max_row, 1).font = BOLD
    sheet.append([])
    sheet.append(["Folder", "Group", "Exclusion", "Value", "Unit", "Lowest kept", "Highest kept", "Left out"])
    header = sheet.max_row
    bold_rows(sheet, (header,))
    for verdict in sorted(verdicts, key=lambda v: v.number):
        exclusion = protocol.exclusions[verdict.number - 1]
        sheet.append([verdict.slice.result.name, group_name(analysis, verdict.slice.group), verdict.number,
                      cell(verdict.value), exclusion.unit(units.get(exclusion.measure, "")), cell(verdict.low),
                      cell(verdict.high), "yes" if verdict.left_out else ("not tested" if verdict.why else "no")])
    sheet.freeze_panes = sheet.cell(header + 1, 2).coordinate
    for letter, width in zip("ABCDEFGH", (40, 18, 10, 12, 8, 13, 13, 11)):
        sheet.column_dimensions[letter].width = width


def _about_sheet(workbook, analysis, protocol, measures, verdicts):
    sheet = workbook.create_sheet("About")
    out = len(left_out(verdicts))
    slices_text = f"{sum(bool(r.recordings) for r in analysis.folders.values())} recording folders, one slice each"
    if protocol.exclusions:
        slices_text += f"; {out} left out by the exclusions (see the Exclusions sheet)"
    units = {m.name: m.unit for m in protocol.recording_measures()}
    exclusions = [("Exclusions" if n == 1 else "", f"{n}. {e.value_text(protocol.condition_label)}; left out when "
                   f"{e.test_text(e.unit(units.get(e.measure, '')))}.") for n, e in enumerate(protocol.exclusions, 1)]
    lines = [
        ("Made by", f"EMA {__version__}, Evoked Analysis, on {datetime.now():%d %B %Y at %H:%M}"),
        ("Protocol", protocol.name),
        ("", protocol.description),
        ("Trace", protocol.trace_explanation()),
        ("ROI file", analysis.roi_file),
        ("Slices", slices_text),
        *exclusions,
        ("Groups", "Slices are grouped by " + (", ".join(analysis.group_by) if analysis.group_by else "nothing (one group)")),
        *label_lines(analysis.labels),
        ("Empty cells", "A measure that could not be measured is left empty, never 0. The Notes sheet says why."),
    ]
    for key, text in lines:
        sheet.append([key, text])
        sheet.cell(sheet.max_row, 1).font = BOLD
    sheet.append([])
    sheet.append(["Measure", "Unit", "What it is"])
    bold_rows(sheet, (sheet.max_row,))
    for measure in measures:
        sheet.append([measure.name, measure.unit, measure.explanation])
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 14
    sheet.column_dimensions["C"].width = 110
    for row in sheet.iter_rows():
        for item in row:
            item.alignment = Alignment(wrap_text=True, vertical="top")
