"""Where EMA keeps what the user makes: saved protocols and detectors, the built documentation, remembered choices."""

from pathlib import Path

PROGRAM_FOLDER = Path(__file__).resolve().parent.parent  # the EMA folder, with EMA.pyw and docs/
USER_PROTOCOLS = PROGRAM_FOLDER / "protocols"
USER_DETECTORS = PROGRAM_FOLDER / "detectors"
DOCUMENTATION = PROGRAM_FOLDER / "docs" / "_build" / "html" / "index.html"
SETTINGS_FILE = Path.home() / ".ema" / "settings.json"  # the last folders and files used, and the labels
