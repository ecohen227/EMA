"""Finding and reading recordings.

A recording is a TIFF movie (frames, rows, columns). A recording folder is any
folder that holds at least one. Recordings are only ever read, never changed.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

import tifffile

# Andor files carry a non-ASCII tag that makes tifffile print a warning per file.
logging.getLogger("tifffile").setLevel(logging.ERROR)

TIFF_SUFFIXES = (".tif", ".tiff")
MIN_MOVIE_BYTES = 1_000_000  # smaller TIFFs are single reference images, not movies
NO_STIM_NAME = re.compile(r"^no\s*\d", re.IGNORECASE)

# The camera the defaults are for: time between frames (ms) and the width of a pixel in the slice (µm).
FRAME_MS = 4.849
PIXEL_UM = 16.0


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

    The first frame of the TIFF is dropped, so frame 0 here is the second
    frame of the file.
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


def has_skip_word(path, words):
    """True if a recording's name holds one of these words, such as 'red' in 'no1 red.tif' or 'hi2_red.tif'."""
    skip = {word.lower() for word in words}
    return bool(skip & set(re.split(r"[\s_\-]+", Path(path).stem.lower())))


def folder_matches(name, only_with, skip_with):
    """True if a folder name passes a folder filter.

    The name must contain at least one of the words in `only_with` (if there
    are any) and none of the words in `skip_with`. Upper and lower case count
    as the same.
    """
    name = name.lower()
    wanted = not only_with or any(word.lower() in name for word in only_with)
    return wanted and not any(word.lower() in name for word in skip_with)


def acquisition_time(path):
    """The time the camera software stored in the TIFF (its DateTime tag), or None if there is none."""
    try:
        with tifffile.TiffFile(path) as tif:
            tag = tif.pages[0].tags.get("DateTime")
            return datetime.strptime(str(tag.value).strip(), "%Y:%m:%d %H:%M:%S") if tag else None
    except (OSError, ValueError, tifffile.TiffFileError):
        return None


def recorded_after(path, candidates, times=None):
    """The candidate recorded right after `path` (by TIFF time stamp), or, if none was, the one right before.

    Returns (partner, reason): the partner's path, or None and a sentence saying why there is none.
    `times` may hold time stamps already read, by path.
    """
    times = {} if times is None else times
    for item in [path, *candidates]:
        if item not in times:
            times[item] = acquisition_time(item)
    if times[path] is None:
        return None, f"{Path(path).name} has no time stamp, so the unstimulated recording made after it is not known."
    timed = sorted((times[c], c) for c in candidates if times[c] is not None)
    if not timed:
        return None, "No unstimulated recording with a time stamp is in the folder."
    after = [c for t, c in timed if t > times[path]]
    return (after[0] if after else timed[-1][1]), ""
