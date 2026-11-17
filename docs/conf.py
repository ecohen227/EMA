"""Sphinx configuration. Build the documentation with:  python -m sphinx docs docs/_build/html"""

import re
from dataclasses import fields
from pathlib import Path

import ema
from ema.evoked.measure_details import BASIC, KINETIC_DETAILS, NEAR_TO_FAR_DETAILS, SLICE, SPATIAL_DETAILS
from ema.evoked.catalogue import KINETIC, NEAR_TO_FAR, SPATIAL, SpatialSettings
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


def settings_table(path, settings_class, group=None, file="file"):
    """A table of the settings of one section (all of them with `group` None), from their declarations
    (see ema/definitions.py), so the documentation can never disagree with the program about a name, a default
    or an explanation."""
    defaults = settings_class()
    lines = [".. list-table::", "   :header-rows: 1", "   :widths: 22 14 44 20", ""]
    lines += ["   * - Setting", "     - Default", "     - What it does", f"     - Name in the {file}"]
    for f in fields(settings_class):
        details = f.metadata
        if group is not None and details["group"] != group:
            continue
        value = getattr(defaults, f.name)
        if details["kind"] == "bool":
            value = "yes" if value else "no"
        elif details["kind"] == "frames":
            value = f"{value[0]} up to {value[1]}"
        elif details["kind"] == "names":
            value = ", ".join(value) or "none"
        elif details["kind"] in ("int", "float"):
            value = f"{value:g} {details['unit']}".strip()
        label = details["label"] + (" (Advanced)" if details.get("advanced") else "")
        lines += [f"   * - {label}", f"     - {value}", f"     - {details['help']}", f"     - ``{f.name}``"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_settings_tables(app):
    """The ROI Selection settings, one table per section."""
    folder = Path(app.srcdir) / "_generated"
    folder.mkdir(exist_ok=True)
    for group in dict.fromkeys(f.metadata["group"] for f in fields(RoiSettings)):
        settings_table(folder / f"settings_{group.lower()}.rst", RoiSettings, group, "ROI file")


def write_metric_tables(app):
    """Tables of the kinetic and spatial measures and of the spatial settings, from ema/evoked/catalogue.py."""
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

    def catalogued(catalogue, details, part):
        lines, group = [], None
        for metric in catalogue:
            if metric.group != group:
                group = metric.group
                lines += [group, "~" * len(group), ""]
            lines += _metric_entry(dict(details[metric.key], title=metric.key, unit=metric.unit,
                                        name=f"``<pulse> {metric.key}``, for example ``P1 {metric.key}``",
                                        definition=metric.explanation.format(pulse="the pulse")), part)
        return lines

    write("basic", [line for entry in BASIC for line in _metric_entry(entry, "evoked")])
    write("kinetic", catalogued(KINETIC, KINETIC_DETAILS, "evoked-kinetic"))
    write("spatial", catalogued(SPATIAL, SPATIAL_DETAILS, "evoked-spatial"))
    write("near_to_far", _metric_entry(dict(NEAR_TO_FAR_DETAILS, title="Near-to-far index", unit=NEAR_TO_FAR.unit,
                                            name="``<comparison> near-to-far``, for example ``PPR near-to-far``",
                                            definition=NEAR_TO_FAR.explanation.format(pulse="(a comparison)")), "evoked"))
    write("slice", [line for entry in SLICE for line in _metric_entry(entry, "evoked-slice")])

    settings_table(folder / "spatial_settings.rst", SpatialSettings, file="protocol file (under spatial › settings)")


def write_spontaneous_tables(app):
    """The detector's settings, group by group, and the reference entries of the spontaneous-event measures."""
    from ema.spontaneous.catalogue import EVENT, RECORDING, SLICE, STATISTICS
    from ema.spontaneous.measure_details import EVENT_DETAILS, RECORDING_DETAILS, SLICE_DETAILS, SUMMARY
    from ema.spontaneous.presets import standard_detector
    from ema.spontaneous.settings import GROUPS, DetectorSettings

    folder = Path(app.srcdir) / "_generated"
    folder.mkdir(exist_ok=True)
    for group in GROUPS:
        settings_table(folder / f"spontaneous_settings_{group.lower().replace(' ', '_')}.rst", DetectorSettings, group,
                       "detector file (under settings)")

    chosen = standard_detector()
    for name, catalogue, details, per, picked in (
        ("event", EVENT, EVENT_DETAILS, "per event", chosen.event_measures),
        ("recording", RECORDING, RECORDING_DETAILS, "per recording", chosen.recording_measures),
        ("slice", SLICE, SLICE_DETAILS, "per slice", chosen.slice_measures),
    ):
        lines, group = [], None
        for measure in catalogue:
            if measure.group != group:
                group = measure.group
                lines += [group, "~" * len(group), ""]
            named = f"``{measure.key}`` ({per}" + ("; chosen in the Standard detector)" if measure.key in picked else ")")
            lines += _metric_entry(dict(details[measure.key], title=measure.key, unit=measure.unit, name=named,
                                        definition=measure.explanation), f"spontaneous-{name}")
        (folder / f"spontaneous_reference_{name}.rst").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = dict(SUMMARY, title="Summaries of event measures", unit="the event measure's unit",
                   name="``<event measure> <statistic>``, for example ``width median``; statistics: " + ", ".join(STATISTICS),
                   definition="The median, mean, smallest or largest value of an event measure over the slice's events.")
    (folder / "spontaneous_reference_summary.rst").write_text("\n".join(_metric_entry(summary, "spontaneous")) + "\n",
                                                             encoding="utf-8")


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

    per_event = load_workbook(EXAMPLES / "Example - Spontaneous per event.xlsx", read_only=True)
    per_slice = load_workbook(EXAMPLES / "Example - Spontaneous per slice.xlsx", read_only=True)
    rows = list(per_event["Events"].iter_rows(values_only=True))
    wanted = ["Folder", "Recording", "Genotype", "Treatment", "Event", "onset (s)", "strength (× noise)", "fitted peak (%)",
              "width (µm)",
              "rise 10-90 (ms)", "half-decay (ms)"]
    columns = [rows[0].index(name) for name in wanted]
    table = [[row[i] for i in columns] for row in rows[:5]] + [["…"] + [""] * (len(wanted) - 1)]
    _write_table(folder / "example_spontaneous_events.rst", table, header=1)
    _write_table(folder / "example_spontaneous_width.rst", list(per_event["width"].iter_rows(min_row=3, values_only=True)), header=1)
    rows = list(per_slice["Slices"].iter_rows(values_only=True))
    wanted = ["Folder", "Genotype", "Treatment", "Recordings searched", "events", "rate (per min)", "sign-flipped rate (per min)",
              "width median (µm)", "half-decay median (ms)"]
    columns = [rows[0].index(name) for name in wanted]
    _write_table(folder / "example_spontaneous_slices.rst", [[row[i] for i in columns] for row in rows], header=1)
    _write_table(folder / "example_spontaneous_rate.rst", list(per_slice["rate"].iter_rows(min_row=3, values_only=True)), header=1)


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


def _metric_entry(entry, part):
    """One measure of the reference page: an anchor to link to (`part` keeps it apart from a measure of the same name
    elsewhere), its title and a list of its fields (the example only if it has one)."""
    anchor = f"{part}-" + re.sub(r"[^a-z0-9]+", "-", entry["title"].lower()).strip("-")
    lines = [f".. _{anchor}:", "", f".. rubric:: {entry['title']}", ""]
    for label, key in FIELDS:
        if entry.get(key):
            lines.append(f":{label}: {entry[key]}")
    return lines + [""]


def setup(app):
    app.connect("builder-inited", write_settings_tables)
    app.connect("builder-inited", write_metric_tables)
    app.connect("builder-inited", write_example_tables)
    app.connect("builder-inited", write_spontaneous_tables)
