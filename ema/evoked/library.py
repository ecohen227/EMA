"""The protocol library: the built-in protocols and the ones saved by the user.

Built-in protocols ship with EMA in `ema/evoked/presets` and cannot be
changed; a changed copy is saved under a new name. Saved protocols are JSON
files in the `protocols` folder of the EMA program folder, one file per
protocol, named after it.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .protocol import Protocol, ProtocolError

PRESETS_FOLDER = Path(__file__).parent / "presets"
USER_FOLDER = Path(__file__).resolve().parents[2] / "protocols"


@dataclass
class Entry:
    """A protocol in the library: where its file is, and whether it is built in."""

    name: str
    path: Path
    built_in: bool

    @property
    def label(self):
        return f"{self.name}  (built in)" if self.built_in else self.name

    def load(self):
        return Protocol.load(self.path)


def entries(user_folder=None):
    """Every protocol in the library: built-in ones first, then saved ones, each by name (2P before 11P)."""
    found = sorted((Entry(*_name_and_path(path), True) for path in PRESETS_FOLDER.glob("*.json")), key=_order)
    folder = user_folder or USER_FOLDER
    if folder.is_dir():
        saved = []
        for path in folder.glob("*.json"):
            try:
                saved.append(Entry(*_name_and_path(path), False))
            except (OSError, ProtocolError):
                continue  # a damaged or foreign file is left alone
        found += sorted(saved, key=_order)
    return found


def _order(entry):
    number = re.match(r"\d+", entry.name)
    return (0, int(number.group()), entry.name.lower()) if number else (1, 0, entry.name.lower())


def _name_and_path(path):
    return Protocol.load(path).name, path


def file_name(name):
    """A file name for a protocol name, without the characters Windows does not allow."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "-", name).strip(" .")
    return f"{cleaned or 'protocol'}.json"


def is_taken(name, user_folder=None, except_path=None):
    """True if another protocol in the library already has this name (ignoring case)."""
    return any(
        entry.name.lower() == name.strip().lower() and entry.path != except_path for entry in entries(user_folder)
    )


def save(protocol, user_folder=None, replacing=None):
    """Save a protocol into the library and return its path.

    `replacing` is the path of the saved protocol it replaces (it may have
    been renamed). Built-in protocols are never replaced.
    """
    folder = user_folder or USER_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file_name(protocol.name)
    protocol.save(path)
    if replacing is not None and Path(replacing) != path and Path(replacing).parent == folder:
        Path(replacing).unlink(missing_ok=True)
    return path


def delete(entry):
    if entry.built_in:
        raise ProtocolError("Built-in protocols cannot be deleted.")
    entry.path.unlink()
