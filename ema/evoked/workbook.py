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
and *About* (the protocol, the labels, and what every measure is).
"""

import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from .. import __version__

PER_RECORDING = "Evoked per recording.xlsx"
PER_SLICE = "Evoked per slice.xlsx"
BOLD = Font(bold=True)
GREY = Font(color="808080", italic=True)


class TablesLocked(OSError):
    """An output file could not be replaced, usually because it is open in Excel."""


@dataclass
class Slice:
    """A measured folder with its labels, its group and its short name."""

    key: str
    result: object  # FolderResult
    labels: dict
    notes: list
    group: tuple  # the values of the grouping labels
    sort_key: tuple
    short_name: str


def write_workbooks(analysis):
    """Write both files into the analysis's output folder. Returns their paths.

    Raises TablesLocked if a file cannot be replaced (open in Excel); the
    other file is still written.
    """
    protocol = analysis.protocol_object()
    slices = _slices(analysis)
    locked = []
    paths = []
    for name, make in ((PER_RECORDING, _per_recording), (PER_SLICE, _per_slice)):
        path = analysis.folder / name
        workbook = make(analysis, protocol, slices)
        temporary = path.with_name(path.stem + ".tmp.xlsx")
        workbook.save(temporary)
        try:
            os.replace(temporary, path)
        except PermissionError:
            temporary.unlink(missing_ok=True)
            locked.append(name)
            continue
        paths.append(path)
    if locked:
        raise TablesLocked(f"{' and '.join(locked)} could not be replaced. Close it in Excel, then write the tables again.")
    return paths


# ---------------------------------------------------------------------------
# Slices and groups
# ---------------------------------------------------------------------------


def _slices(analysis):
    labels = analysis.labels
    grouping = [labels.label(name) for name in analysis.group_by if labels.label(name)]
    numbers = [label for label in labels.labels if label.is_number and label not in grouping]
    found = []
    for key, result in analysis.folders.items():
        if not result.recordings:
            continue
        read = analysis.folder_labels(result)
        values = read.values
        group = tuple(values[label.name] for label in grouping)
        sort_key = (
            tuple(label.sort_key(values[label.name]) for label in grouping),
            tuple(label.sort_key(values[label.name]) for label in labels.labels),
            result.name.lower(),
        )
        named = [f"{label.name} {values[label.name]}" for label in numbers if values[label.name]]
        short = " ".join(named) if named else "/".join(Path(result.name).parts[-2:])
        notes = list(read.notes) + [f"No {label.name} in the folder names." for label in grouping if not values[label.name]]
        found.append(Slice(key, result, values, notes, group, sort_key, short))
    return sorted(found, key=lambda s: s.sort_key)


def _group_name(analysis, group):
    names = [name for name in analysis.group_by if analysis.labels.label(name)]
    return " ".join(value or f"(no {name})" for name, value in zip(names, group)) or "All slices"


def _groups(analysis, slices):
    """{group name: [slices]} in the order of the labels' values."""
    groups = {}
    for item in slices:
        groups.setdefault(_group_name(analysis, item.group), []).append(item)
    return groups


# ---------------------------------------------------------------------------
# The two files
# ---------------------------------------------------------------------------


def _per_recording(analysis, protocol, slices):
    workbook = Workbook()
    measures = [m for m in protocol.measures() if m.per == "recording"]
    label_names = analysis.labels.names()
    partner = ["Unstimulated partner"] if protocol.uses_partner else []

    sheet = workbook.active
    sheet.title = "Recordings"
    header = ["Folder", "Recording", *partner, *label_names, protocol.condition_label, "ROI reviewed"]
    sheet.append(header + [_heading(m) for m in measures])
    for item in slices:
        for recording in _ordered(item.result.recordings):
            row = [item.result.name, recording.file] + ([recording.partner] if partner else [])
            row += [item.labels[name] for name in label_names]
            row += [recording.condition, "yes" if item.result.reviewed else "no"]
            sheet.append(row + [_cell(recording.values.get(m.name)) for m in measures])
    _finish_table(sheet, len(header))

    notes = []
    names = _sheet_names(m.name for m in measures)
    groups = _groups(analysis, slices)
    width = max((len(members) for members in groups.values()), default=1)
    rows = _condition_rows(slices)
    for item in slices:
        notes += _row_notes(item, _with_conditions(slices))
    for measure in measures:
        sheet = workbook.create_sheet(names[measure.name])
        _title(sheet, _heading(measure), f"Prism: Grouped table, {width} replicates side by side. Copy from A5 to the "
               "last value; paste at the first row title.")
        top = ["" for _ in range(1 + width * len(groups))]
        names_row = [protocol.condition_label] + [""] * (width * len(groups))
        for g, (group, members) in enumerate(groups.items()):
            top[1 + g * width] = group
            for s, member in enumerate(members):
                names_row[1 + g * width + s] = member.short_name
        sheet.append(top)
        sheet.append(names_row)
        for row_key, title in rows:
            line = [title]
            for members in groups.values():
                values = [_cell(_value_at(member, row_key, measure.name)) for member in members]
                line += values + [None] * (width - len(values))
            sheet.append(line)
        _bold_rows(sheet, (3, 4))
        sheet.freeze_panes = "B5"

    notes += _notes(slices, per_recording=True)
    _notes_sheet(workbook, notes)
    _about_sheet(workbook, analysis, protocol, measures, "recording")
    return workbook


def _per_slice(analysis, protocol, slices):
    workbook = Workbook()
    measures = [m for m in protocol.measures() if m.per == "slice"]
    label_names = analysis.labels.names()

    sheet = workbook.active
    sheet.title = "Slices"
    header = ["Folder", *label_names, "Recordings measured", "ROI reviewed"]
    sheet.append(header + [_heading(m) for m in measures])
    for item in slices:
        row = [item.result.name] + [item.labels[name] for name in label_names]
        row += [len(item.result.recordings), "yes" if item.result.reviewed else "no"]
        sheet.append(row + [_cell(item.result.summary.get(m.name)) for m in measures])
    _finish_table(sheet, len(header))
    if not measures:
        sheet.append([])
        sheet.append(["The protocol has no per-slice measures. Choose them in the configurator, under Summary."])

    names = _sheet_names(m.name for m in measures)
    rows_label = analysis.labels.label(analysis.slice_rows_by) if analysis.slice_rows_by not in analysis.group_by else None
    groups = _groups(analysis, slices)
    for measure in measures:
        sheet = workbook.create_sheet(names[measure.name])
        if rows_label is None:
            _column_table(sheet, measure, groups)
        else:
            _grouped_by_label(sheet, measure, groups, rows_label, slices)

    _notes_sheet(workbook, _notes(slices, per_recording=False))
    _about_sheet(workbook, analysis, protocol, measures, "slice")
    return workbook


def _column_table(sheet, measure, groups):
    _title(sheet, _heading(measure), "Prism: Column table. Copy from A4 to the last value; paste at the first value.")
    sheet.append(list(groups))
    columns = [[_cell(m.result.summary.get(measure.name)) for m in members] for members in groups.values()]
    for i in range(max((len(c) for c in columns), default=0)):
        sheet.append([column[i] if i < len(column) else None for column in columns])
    _bold_rows(sheet, (3,))
    sheet.freeze_panes = "A4"


def _grouped_by_label(sheet, measure, groups, label, slices):
    values = sorted({s.labels[label.name] for s in slices}, key=label.sort_key)
    width = max((sum(m.labels[label.name] == v for m in members) for members in groups.values() for v in values), default=1)
    _title(sheet, _heading(measure), f"Prism: Grouped table, {width} replicates side by side. Copy from A5 to the "
           "last value; paste at the first row title.")
    top = [""] * (1 + width * len(groups))
    for g, group in enumerate(groups):
        top[1 + g * width] = group
    sheet.append(top)
    sheet.append([label.name])
    for value in values:
        line = [value or f"(no {label.name})"]
        for members in groups.values():
            cells = [_cell(m.result.summary.get(measure.name)) for m in members if m.labels[label.name] == value]
            line += cells + [None] * (width - len(cells))
        sheet.append(line)
    _bold_rows(sheet, (3, 4))
    sheet.freeze_panes = "B5"


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


def _with_conditions(slices):
    """True when any recording has a condition: the rows of the measure sheets are then the conditions only."""
    return any(r.condition is not None for s in slices for r in s.result.recordings)


def _condition_rows(slices):
    """(row key, row title) of every condition of any slice, in order; file names when no recording has a condition."""
    if _with_conditions(slices):
        keys = sorted({r.condition for s in slices for r in s.result.recordings if r.condition is not None})
    else:
        keys = sorted({r.file for s in slices for r in s.result.recordings}, key=str.lower)
    return [(k, k) for k in keys]


def _value_at(item, row_key, name):
    """The value of a measure in the slice's recording for this row (the plainest name, if several)."""
    recording = next((r for r in _ordered(item.result.recordings) if _row_key(r) == row_key), None)
    return None if recording is None else recording.values.get(name)


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


def _notes(slices, per_recording):
    notes = []
    for item in slices:
        notes += [[item.result.name, "", note] for note in item.notes]
        for file, why in item.result.skipped:
            notes.append([item.result.name, file, f"Not measured: {why}"])
        if per_recording:
            for recording in item.result.recordings:
                notes += [[item.result.name, recording.file, problem] for problem in recording.problems]
    return notes


def _notes_sheet(workbook, notes):
    sheet = workbook.create_sheet("Notes")
    sheet.append(["Folder", "Recording", "Note"])
    for note in notes:
        sheet.append(note)
    if not notes:
        sheet.append(["Nothing to note: every recording was measured."])
    _finish_table(sheet, 3)
    sheet.column_dimensions["C"].width = 100


def _about_sheet(workbook, analysis, protocol, measures, per):
    sheet = workbook.create_sheet("About")
    labels = analysis.labels
    lines = [
        ("Made by", f"EMA {__version__}, Evoked Analysis, on {datetime.now():%d %B %Y at %H:%M}"),
        ("Protocol", protocol.name),
        ("", protocol.description),
        ("Trace", protocol.trace_explanation()),
        ("ROI file", analysis.roi_file),
        ("Slices", f"{sum(bool(r.recordings) for r in analysis.folders.values())} recording folders, one slice each"),
        ("Groups", "Slices are grouped by " + (", ".join(analysis.group_by) if analysis.group_by else "nothing (one group)")),
        ("Labels", "Read from the folder names of each recording folder, innermost first; the first folder that holds a "
                   "label gives its value."),
    ]
    for label in labels.labels:
        if label.is_number:
            lines.append(("", f"{label.name}: the number in {', '.join(label.patterns)} (# stands for the number)"))
        else:
            spelled = "; ".join(f"{value} = {', '.join(spellings)}" for value, spellings in label.values.items())
            lines.append(("", f"{label.name}: {spelled}"))
    lines.append(("Empty cells", "A measure that could not be measured is left empty, never 0. The Notes sheet says why."))
    for key, text in lines:
        sheet.append([key, text])
        sheet.cell(sheet.max_row, 1).font = BOLD
    sheet.append([])
    sheet.append(["Measure", "Unit", "What it is"])
    _bold_rows(sheet, (sheet.max_row,))
    for measure in measures:
        sheet.append([measure.name, measure.unit, measure.explanation])
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 14
    sheet.column_dimensions["C"].width = 110
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _heading(measure):
    return f"{measure.name} ({measure.unit})" if measure.unit else measure.name


def _cell(value):
    if value is None or isinstance(value, str):
        return value
    value = float(value)
    return value if math.isfinite(value) else None


def _title(sheet, title, hint):
    sheet.append([title])
    sheet.append([hint])
    sheet.cell(1, 1).font = Font(bold=True, size=12)
    sheet.cell(2, 1).font = GREY


def _bold_rows(sheet, rows):
    for row in rows:
        for cell in sheet[row]:
            cell.font = BOLD


def _finish_table(sheet, label_columns):
    _bold_rows(sheet, (1,))
    sheet.freeze_panes = sheet.cell(2, min(label_columns, 2) + 1).coordinate
    for index, column in enumerate(sheet.iter_cols(max_row=min(sheet.max_row, 200)), start=1):
        longest = max((len(str(cell.value)) for cell in column if cell.value is not None), default=8)
        sheet.column_dimensions[column[0].column_letter].width = min(max(longest + 2, 8), 60)


def _sheet_names(names):
    """A sheet name for each measure: at most 31 characters, without the characters Excel forbids, all different."""
    found, taken = {}, {"recordings", "slices", "notes", "about"}
    for name in names:
        base = re.sub(r"[\[\]:*?\\]", "-", name.replace("/", "÷"))[:31].strip("'") or "Measure"
        candidate, n = base, 2
        while candidate.lower() in taken:
            suffix = f" ({n})"
            candidate, n = base[: 31 - len(suffix)] + suffix, n + 1
        taken.add(candidate.lower())
        found[name] = candidate
    return found
