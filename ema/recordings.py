"""Finding and reading recordings.

A recording is a TIFF movie (frames, rows, columns). A recording folder is any
folder that holds at least one. Recordings are only ever read, never changed.
"""

import io
import logging
import os
import re
import threading
from collections import OrderedDict
from concurrent.futures import CancelledError, ThreadPoolExecutor
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

    The file is read from disk in one go and then decoded. Decoding it from
    the disk directly would read it in thousands of small pieces, which is
    several times slower, and very slow from network, cloud or USB drives.

    The first frame of the TIFF is dropped, so frame 0 here is the second
    frame of the file.
    """
    try:
        stack = tifffile.imread(io.BytesIO(Path(path).read_bytes()))
    except tifffile.TiffFileError as error:
        raise ValueError(f"{Path(path).name} cannot be read as a TIFF ({error}).") from error
    if stack.ndim != 3:
        raise ValueError(f"{Path(path).name} is not a movie (its shape is {stack.shape}).")
    return stack[1:]


class RecordingCache:
    """Reads recordings with `load` and keeps the last `size` in memory; call it like `load_stack`.

    `read_ahead(paths)` reads recordings in a background thread, so that
    they are ready by the time they are wanted. `resize(size)` keeps fewer or
    more. `stop()` drops what is waiting to be read and empties the cache for
    good: recordings asked for afterwards are read but no longer kept.
    """

    def __init__(self, size, load=load_stack):
        self.size = size
        self._load = load
        self._stacks = OrderedDict()  # path -> stack, the most recently used last
        self._reading = {}  # path -> Future of a read ahead
        self._lock = threading.Lock()
        self._reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix="EMA read-ahead")
        self._stopped = False

    def __call__(self, path):
        path = Path(path)
        with self._lock:
            if path in self._stacks:
                self._stacks.move_to_end(path)
                return self._stacks[path]
            reading = self._reading.get(path)
        stack = None
        if reading is not None:
            try:
                stack = reading.result()
            except CancelledError:  # dropped by stop() before it was read: read it now
                stack = None
        if stack is None:
            stack = self._load(path)
        self._keep(path, stack)
        return stack

    def read_ahead(self, paths):
        with self._lock:
            if self._stopped:
                return
            for path in map(Path, paths):
                if path not in self._stacks and path not in self._reading:
                    self._reading[path] = self._reader.submit(self._read, path)

    def resize(self, size):
        """Keep at most `size` recordings from now on; the least recently used go first."""
        with self._lock:
            self.size = size
            self._trim()

    def stop(self):
        with self._lock:
            self._stopped = True
            self._reader.shutdown(wait=False, cancel_futures=True)
            self._reading.clear()
            self._stacks.clear()

    def _read(self, path):
        try:
            stack = self._load(path)
            self._keep(path, stack)
            return stack
        finally:
            with self._lock:
                self._reading.pop(path, None)

    def _keep(self, path, stack):
        with self._lock:
            if self._stopped:
                return
            self._stacks[path] = stack
            self._stacks.move_to_end(path)
            self._trim()

    def _trim(self):
        while len(self._stacks) > self.size:
            self._stacks.popitem(last=False)


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
