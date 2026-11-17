"""A library of protocols or of detectors: the built-in ones and the ones the user saved.

Built-in ones ship with EMA (in ema/evoked/built_in and ema/spontaneous/built_in)
and cannot be changed: a changed copy is saved under a new name. Saved ones are
JSON files in the `protocols` or `detectors` folder of the EMA folder, one file
each, named after it. The two libraries are ema.evoked.presets.LIBRARY and
ema.spontaneous.presets.LIBRARY.
"""

import re
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass
class Entry:
    """A protocol or detector in a library: its name, its file, and whether it is built in."""

    name: str
    path: Path
    built_in: bool

    @property
    def label(self):
        return f"{self.name}  (built in)" if self.built_in else self.name


@dataclass(frozen=True)
class Library:
    noun: str  # "protocol" or "detector"
    load: object  # load(path) -> the protocol or detector; raises OSError or ValueError
    built_in: Path  # the folder of the built-in ones
    saved: Path  # the folder of the user's

    def in_folder(self, folder):
        """The same library with the user's files in another folder (None: its own)."""
        return self if folder is None else replace(self, saved=Path(folder))

    def entries(self):
        """Every entry: built-in ones first, then saved ones, each by name (2P before 11P).

        A file that cannot be read, or is not a protocol or detector, is left out.
        """
        found = []
        for folder, built_in in ((self.built_in, True), (self.saved, False)):
            readable = []
            for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
                try:
                    readable.append(Entry(self.load(path).name, path, built_in))
                except (OSError, ValueError):
                    continue
            found += sorted(readable, key=_order)
        return found

    def is_taken(self, name, except_path=None):
        """True if another entry already has this name (upper and lower case count as the same)."""
        return any(e.name.lower() == name.strip().lower() and e.path != except_path for e in self.entries())

    def save(self, item, replacing=None):
        """Save a protocol or detector and return its path. `replacing` is the saved file it replaces (it may have
        been renamed); built-in files are never replaced."""
        self.saved.mkdir(parents=True, exist_ok=True)
        path = self.saved / file_name(item.name, self.noun)
        item.save(path)
        if replacing is not None and Path(replacing) != path and Path(replacing).parent == self.saved:
            Path(replacing).unlink(missing_ok=True)
        return path

    def delete(self, entry):
        if entry.built_in:
            raise ValueError(f"Built-in {self.noun}s cannot be deleted.")
        entry.path.unlink(missing_ok=True)


def file_name(name, noun="file"):
    """A file name for a protocol or detector name, without the characters Windows does not allow."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "-", name).strip(" .")
    return f"{cleaned or noun}.json"


def _order(entry):
    number = re.match(r"\d+", entry.name)
    return (0, int(number.group()), entry.name.lower()) if number else (1, 0, entry.name.lower())
