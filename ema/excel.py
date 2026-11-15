"""What the Excel files of the evoked and the spontaneous analysis share: slices and their groups, Prism tables, saving.

A slice is a measured recording folder with the labels read from its folder
names. Slices are grouped by the values of the labels the user ticked, in
the order of those values; Prism sheets put the groups side by side.
"""

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl.styles import Font

BOLD = Font(bold=True)
GREY = Font(color="808080", italic=True)
RESERVED = {"events", "recordings", "slices", "notes", "about"}


class TablesLocked(OSError):
    """An output file could not be replaced, usually because it is open in Excel."""


@dataclass
class Slice:
    """A measured folder with its labels, its group and its short name."""

    key: str
    result: object  # the folder's result
    labels: dict
    notes: list
    group: tuple  # the values of the grouping labels
    sort_key: tuple
    short_name: str


def slices(analysis):
    """Every measured folder of an analysis (with at least one recording), in the order of its group and labels."""
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


def group_name(analysis, group):
    names = [name for name in analysis.group_by if analysis.labels.label(name)]
    return " ".join(value or f"(no {name})" for name, value in zip(names, group)) or "All slices"


def groups(analysis, found):
    """{group name: [slices]} in the order of the labels' values."""
    by_group = {}
    for item in found:
        by_group.setdefault(group_name(analysis, item.group), []).append(item)
    return by_group


def save_workbooks(folder, books):
    """Save {file name: workbook} into a folder, each through a temporary file. Returns the paths written.

    Raises TablesLocked if a file cannot be replaced (open in Excel); the
    others are still written.
    """
    locked, paths = [], []
    for name, workbook in books.items():
        path = Path(folder) / name
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


def label_lines(labels):
    """The About sheet's description of the labels: (key, text) lines."""
    lines = [("Labels", "Read from the folder names of each recording folder, innermost first; the first folder that holds "
                        "a label gives its value.")]
    for label in labels.labels:
        if label.is_number:
            lines.append(("", f"{label.name}: the number in {', '.join(label.patterns)} (# stands for the number)"))
        else:
            spelled = "; ".join(f"{value} = {', '.join(spellings)}" for value, spellings in label.values.items())
            lines.append(("", f"{label.name}: {spelled}"))
    return lines


def column_table(sheet, title, columns):
    """A Prism column table: the title, how to paste, the column titles in row 3 and the values from row 4."""
    write_title(sheet, title, "Prism: Column table. Copy from A4 to the last value; paste at the first value.")
    sheet.append(list(columns))
    values = [[cell(v) for v in column] for column in columns.values()]
    for i in range(max((len(c) for c in values), default=0)):
        sheet.append([column[i] if i < len(column) else None for column in values])
    bold_rows(sheet, (3,))
    sheet.freeze_panes = "A4"


def grouped_table(sheet, title, label, by_group):
    """A Prism grouped table: one row per value of a label, a group of side-by-side columns per group.

    `by_group` is {group name: [(the label's value, value)]}.
    """
    rows = sorted({row for pairs in by_group.values() for row, _ in pairs}, key=label.sort_key)
    width = max((sum(r == row for r, _ in pairs) for pairs in by_group.values() for row in rows), default=1)
    write_title(sheet, title, f"Prism: Grouped table, {width} replicates side by side. Copy from A5 to the last value; "
                              "paste at the first row title.")
    top = [""] * (1 + width * len(by_group))
    for g, group in enumerate(by_group):
        top[1 + g * width] = group
    sheet.append(top)
    sheet.append([label.name])
    for row in rows:
        line = [row or f"(no {label.name})"]
        for pairs in by_group.values():
            cells = [cell(v) for r, v in pairs if r == row]
            line += cells + [None] * (width - len(cells))
        sheet.append(line)
    bold_rows(sheet, (3, 4))
    sheet.freeze_panes = "B5"


def notes_sheet(workbook, notes, empty="Nothing to note: every recording was measured."):
    sheet = workbook.create_sheet("Notes")
    sheet.append(["Folder", "Recording", "Note"])
    for note in notes:
        sheet.append(note)
    if not notes:
        sheet.append([empty])
    finish_table(sheet, 3)
    sheet.column_dimensions["C"].width = 100


def heading(name, unit):
    return f"{name} ({unit})" if unit else name


def cell(value):
    """A value as a cell: numbers as floats, NaN as an empty cell, text as it is."""
    if value is None or isinstance(value, str):
        return value
    value = float(value)
    return value if math.isfinite(value) else None


def write_title(sheet, title, hint):
    sheet.append([title])
    sheet.append([hint])
    sheet.cell(1, 1).font = Font(bold=True, size=12)
    sheet.cell(2, 1).font = GREY


def bold_rows(sheet, rows):
    for row in rows:
        for item in sheet[row]:
            item.font = BOLD


def finish_table(sheet, label_columns):
    """Bold headings, the first columns frozen, and column widths that fit their contents."""
    bold_rows(sheet, (1,))
    sheet.freeze_panes = sheet.cell(2, min(label_columns, 2) + 1).coordinate
    for column in sheet.iter_cols(max_row=min(sheet.max_row, 200)):
        longest = max((len(str(c.value)) for c in column if c.value is not None), default=8)
        sheet.column_dimensions[column[0].column_letter].width = min(max(longest + 2, 8), 60)


def sheet_names(names):
    """A sheet name for each measure: at most 31 characters, without the characters Excel forbids, all different."""
    found, taken = {}, set(RESERVED)
    for name in names:
        base = re.sub(r"[\[\]:*?\\]", "-", name.replace("/", "÷"))[:31].strip("'") or "Measure"
        candidate, n = base, 2
        while candidate.lower() in taken:
            suffix = f" ({n})"
            candidate, n = base[: 31 - len(suffix)] + suffix, n + 1
        taken.add(candidate.lower())
        found[name] = candidate
    return found
