"""Finding and reading recordings.

A recording is a TIFF movie (frames, rows, columns). A recording folder is any
folder that holds at least one. Recordings are only ever read, never changed.
"""

import logging
import os
import re
from pathlib import Path

import tifffile

# Andor files carry a non-ASCII tag that makes tifffile print a warning per file.
logging.getLogger("tifffile").setLevel(logging.ERROR)

TIFF_SUFFIXES = (".tif", ".tiff")
MIN_MOVIE_BYTES = 1_000_000  # smaller TIFFs are single reference images, not movies
NO_STIM_NAME = re.compile(r"^no\s*\d", re.IGNORECASE)
ONLINE_ONLY = 0x400000 | 0x1000  # Windows attributes of a OneDrive file that is not downloaded


def list_recordings(folder):
    """The TIFF movies in a folder: numbered names first (50uA, 100uA, ...), then the rest by name."""
    paths = [
        path
        for path in Path(folder).iterdir()
        if path.suffix.lower() in TIFF_SUFFIXES and path.stat().st_size >= MIN_MOVIE_BYTES
    ]
    return sorted(paths, key=_sort_key)


def _sort_key(path):
    number = re.match(r"\d+", path.name)
    return (0, int(number.group()), path.name.lower()) if number else (1, 0, path.name.lower())


def find_recording_folders(root):
    """Every folder under root (root included) that holds at least one TIFF movie."""
    folders = []
    for folder, _, names in os.walk(root):
        if any(name.lower().endswith(TIFF_SUFFIXES) for name in names) and list_recordings(folder):
            folders.append(Path(folder))
    return sorted(folders, key=lambda folder: str(folder).lower())


def load_stack(path):
    """Read a recording as an array (frames, rows, columns).

    The first frame of the TIFF is dropped, as in every earlier EMA version,
    so frame 0 here is the second frame of the file.
    """
    try:
        stack = tifffile.imread(path)
    except tifffile.TiffFileError as error:
        raise ValueError(f"{Path(path).name} cannot be read as a TIFF ({error}).") from error
    if stack.ndim != 3:
        raise ValueError(f"{Path(path).name} is not a movie (its shape is {stack.shape}).")
    return stack[1:]


def is_no_stim(path):
    """True for unstimulated trials such as 'no3.tif' or 'no1 red.tif'."""
    return bool(NO_STIM_NAME.match(Path(path).name))


def is_online_only(path):
    """True for a OneDrive file that is not on this computer yet. Reading it would download it."""
    return bool(getattr(os.stat(path), "st_file_attributes", 0) & ONLINE_ONLY)
