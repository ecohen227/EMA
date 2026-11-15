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
