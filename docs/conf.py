"""Sphinx configuration. Build the documentation with:  python -m sphinx docs docs/_build/html"""

from dataclasses import fields
from pathlib import Path

import ema
from ema.evoked.metric_details import BASIC, KINETIC_DETAILS, NEAR_TO_FAR_DETAILS, SLICE, SPATIAL_DETAILS
from ema.evoked.metrics import KINETIC, NEAR_TO_FAR, SPATIAL, SpatialSettings
from ema.roi_selection import RoiSettings

project = "EMA"
author = "Milnerwood lab"
release = ema.__version__
extensions = ["sphinx.ext.autodoc"]
exclude_patterns = ["_build", "_generated"]
html_theme = "furo"
html_title = f"EMA {release}"
autodoc_member_order = "bysource"
numfig = True


def write_settings_tables(app):
    """Write one table per group of settings from the list in ema/roi_selection/settings.py.

    The settings page includes these tables, so the documentation can never
    disagree with the program about a name, a default or an explanation.
    """
    folder = Path(app.srcdir) / "_generated"
    folder.mkdir(exist_ok=True)
    defaults = RoiSettings()
    groups = {}
    for f in fields(RoiSettings):
        groups.setdefault(f.metadata["group"], []).append(f)
    for group, settings in groups.items():
        lines = [".. list-table::", "   :header-rows: 1", "   :widths: 22 14 44 20", ""]
        lines += ["   * - Setting", "     - Default", "     - What it does", "     - Name in the ROI file"]
        for f in settings:
            value = getattr(defaults, f.name)
            if f.metadata["kind"] == "frames":
                value = f"{value[0]} up to {value[1]}"
            elif isinstance(value, list):
                value = ", ".join(value)
            lines += [
                f"   * - {f.metadata['label']}",
                f"     - {value} {f.metadata['unit']}",
                f"     - {f.metadata['help']}",
                f"     - ``{f.name}``",
            ]
        (folder / f"settings_{group.lower()}.rst").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_metric_tables(app):
    """Tables of the kinetic and spatial measures and of the spatial settings, from ema/evoked/metrics.py."""
    folder = Path(app.srcdir) / "_generated"
    folder.mkdir(exist_ok=True)
    for name, catalogue in (("kinetic", KINETIC), ("spatial", SPATIAL + [NEAR_TO_FAR])):
        lines = [".. list-table::", "   :header-rows: 1", "   :widths: 20 12 18 50", ""]
        lines += ["   * - Measure", "     - Unit", "     - Group", "     - Definition"]
        for metric in catalogue:
            explanation = metric.explanation.format(pulse="the pulse" if metric is not NEAR_TO_FAR else "(a comparison)")
            lines += [f"   * - {metric.key}", f"     - {metric.unit}", f"     - {metric.group}", f"     - {explanation}"]
        (folder / f"{name}_measures.rst").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # The measure reference page: one entry per measure, in five parts that the page introduces in turn
    def write(name, lines):
        (folder / f"reference_{name}.rst").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def catalogued(catalogue, details):
        lines, group = [], None
        for metric in catalogue:
            if metric.group != group:
                group = metric.group
                lines += [group, "~" * len(group), ""]
            lines += _metric_entry(dict(details[metric.key], title=metric.key, unit=metric.unit,
                                        name=f"``<pulse> {metric.key}``, for example ``P1 {metric.key}``",
                                        definition=metric.explanation.format(pulse="the pulse")))
        return lines

    write("basic", [line for entry in BASIC for line in _metric_entry(entry)])
    write("kinetic", catalogued(KINETIC, KINETIC_DETAILS))
    write("spatial", catalogued(SPATIAL, SPATIAL_DETAILS))
    write("near_to_far", _metric_entry(dict(NEAR_TO_FAR_DETAILS, title="Near-to-far index", unit=NEAR_TO_FAR.unit,
                                            name="``<comparison> near-to-far``, for example ``PPR near-to-far``",
                                            definition=NEAR_TO_FAR.explanation.format(pulse="(a comparison)"))))
    write("slice", [line for entry in SLICE for line in _metric_entry(entry)])

    defaults = SpatialSettings()
    lines = [".. list-table::", "   :header-rows: 1", "   :widths: 25 15 60", ""]
    lines += ["   * - Setting", "     - Default", "     - What it does"]
    for f in fields(SpatialSettings):
        value = getattr(defaults, f.name)
        value = ("yes" if value else "no") if isinstance(value, bool) else f"{value:g} {f.metadata['unit']}"
        lines += [f"   * - {f.metadata['label']}", f"     - {value}", f"     - {f.metadata['help']}"]
    (folder / "spatial_settings.rst").write_text("\n".join(lines) + "\n", encoding="utf-8")


EXAMPLES = Path(__file__).parent / "examples"


def write_example_tables(app):
    """Excerpts of the example Excel files (made by make_screenshots.py from made-up recordings), as tables."""
    from openpyxl import load_workbook

    folder = Path(app.srcdir) / "_generated"
    folder.mkdir(exist_ok=True)
    per_recording = load_workbook(EXAMPLES / "Example - Evoked per recording.xlsx", read_only=True)
    per_slice = load_workbook(EXAMPLES / "Example - Evoked per slice.xlsx", read_only=True)

    rows = list(per_recording["Recordings"].iter_rows(values_only=True))
    wanted = ["Folder", "Recording", "Unstimulated partner", "Genotype", "Treatment", "Animal", "Slice",
              "Current (µA)", "P1 response (%)", "PPR (ratio)", "Tau (ms)"]
    columns = [rows[0].index(name) for name in wanted]
    table = [[row[i] for i in columns] for row in rows[:4]] + [["…"] + [""] * (len(wanted) - 1)]
    _write_table(folder / "example_recordings.rst", table, header=1)
    # the measure sheets from row 3 on: rows 1 and 2 hold the measure's name and how to paste it
    _write_table(folder / "example_prism_recording.rst", list(per_recording["P1 response"].iter_rows(min_row=3, values_only=True)), header=2)
    _write_table(folder / "example_prism_slice.rst", list(per_slice["P1 response mean 100-400"].iter_rows(min_row=3, values_only=True)), header=1)


def _write_table(path, rows, header):
    """A list-table of spreadsheet rows, the first `header` of them bold; numbers with two decimals."""
    def text(value):
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value).replace("*", "\\*")

    rows = [row for row in rows if any(cell is not None for cell in row)]
    width = max(len(row) for row in rows)
    lines = [".. list-table::", f"   :header-rows: {header}", ""]
    for row in rows:
        cells = [text(cell) for cell in row] + [""] * (width - len(row))
        lines.append(f"   * - {cells[0]}".rstrip())
        lines += [f"     - {cell}".rstrip() for cell in cells[1:]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


FIELDS = [("Named", "name"), ("Unit", "unit"), ("Definition", "definition"), ("Formula", "formula"),
          ("How", "method"), ("Empty when", "empty"), ("What it reflects", "meaning"), ("Be careful", "caveats"),
          ("Example", "example")]


def _metric_entry(entry):
    """One measure of the reference page: its title and a list of its fields (the example only if it has one)."""
    lines = [f".. rubric:: {entry['title']}", ""]
    for label, key in FIELDS:
        if entry.get(key):
            lines.append(f":{label}: {entry[key]}")
    return lines + [""]


def setup(app):
    app.connect("builder-inited", write_settings_tables)
    app.connect("builder-inited", write_metric_tables)
    app.connect("builder-inited", write_example_tables)
