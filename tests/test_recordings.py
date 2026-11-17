import numpy as np
import pytest
import tifffile

from ema.recordings import RecordingCache, find_recording_folders, is_no_stim, list_recordings, load_stack

from conftest import FRAMES, SHAPE


def test_finds_only_folders_with_movies(recordings, io_folder, train_folder):
    # "Slice 1" holds only a single reference image, so it is not a recording folder
    assert find_recording_folders(recordings) == [train_folder, io_folder]


def test_recordings_are_listed_by_current_then_name(io_folder):
    assert [path.name for path in list_recordings(io_folder)] == ["100uA.tif", "200uA.tif", "300uA.tif", "no1.tif"]


def test_first_frame_is_dropped(io_folder):
    stack = load_stack(io_folder / "200uA.tif")
    assert stack.shape == (FRAMES, *SHAPE)
    assert np.array_equal(stack[0], tifffile.imread(io_folder / "200uA.tif")[1])


def test_the_recording_cache_reads_each_recording_once(io_folder):
    reads = []
    cache = RecordingCache(2, load=lambda path: reads.append(path.name) or load_stack(path))
    first, second, third = list_recordings(io_folder)[:3]
    cache.read_ahead([first, second])
    stack = cache(first)
    assert np.array_equal(stack, load_stack(first)) and cache(first) is stack
    cache(second)
    assert sorted(reads) == [first.name, second.name]  # read ahead, and not again when wanted
    cache(third)  # only two are kept: the least recently used goes
    cache(first)
    assert reads.count(first.name) == 2
    with pytest.raises(OSError):
        cache(io_folder / "missing.tif")
    cache.stop()


def test_single_image_is_not_a_movie(recordings):
    with pytest.raises(ValueError, match="not a movie"):
        load_stack(recordings / "Animal 1" / "Slice 1" / "reference.tif")


def test_no_stim_names():
    assert is_no_stim("no3.tif") and is_no_stim("No1 red.tif")
    assert not is_no_stim("300uA.tif") and not is_no_stim("november.tif")
