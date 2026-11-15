"""Sphinx configuration. Build the documentation with:  python -m sphinx docs docs/_build/html"""

from dataclasses import fields
from pathlib import Path

import ema
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


def setup(app):
    app.connect("builder-inited", write_settings_tables)
