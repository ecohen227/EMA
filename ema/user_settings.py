"""Small things EMA remembers between runs, such as the last folders used.

They live in one JSON file in the user's home folder: ~/.ema/settings.json
"""

import json
from pathlib import Path

FILE = Path.home() / ".ema" / "settings.json"


def remembered(name, default=""):
    try:
        return json.loads(FILE.read_text(encoding="utf-8")).get(name, default)
    except (OSError, ValueError):
        return default


def remember(**values):
    try:
        saved = json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    saved.update(values)
    try:
        FILE.parent.mkdir(exist_ok=True)
        FILE.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    except OSError:
        pass  # remembering is a convenience; never stop the program for it
