"""Synthetic recordings with a known release centre and electrode, so every test knows the right answer."""

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
import tifffile

SHAPE = (64, 64)
FRAMES = 330
CENTER = (44, 30)  # (x, y) of the strongest response
STIM_FRAME = 103
ELECTRODE = np.zeros(SHAPE, bool)
ELECTRODE[29:36, 0:34] = True


def make_recording(path, response=0.5, seed=0, clock="10:00:00"):
    """Write a movie: flat tissue, a dark electrode from the left, and a response that decays after the stimulus.

    `clock` is the time stamp the camera software would store (on 5 December 2025)."""
    rng = np.random.default_rng(seed)
    y, x = np.indices(SHAPE)
    f0 = np.where(ELECTRODE, 150.0, 500.0)
    spot = np.exp(-((x - CENTER[0]) ** 2 + (y - CENTER[1]) ** 2) / (2 * 8.0**2)) * ~ELECTRODE
    time = np.arange(FRAMES + 1) - (STIM_FRAME + 1)  # +1: the first frame of the file is dropped on loading
    course = np.where(time >= 0, np.exp(-time / 30.0), 0.0)
    movie = f0 * (1 + response * course[:, None, None] * spot) + rng.normal(0, 8, (FRAMES + 1, *SHAPE))
    stamp = datetime.strptime(f"2025:12:05 {clock}", "%Y:%m:%d %H:%M:%S")
    tifffile.imwrite(path, movie.clip(0).astype(np.uint16), datetime=stamp)


@pytest.fixture(scope="session")
def recordings(tmp_path_factory):
    """A small study: one slice with a paired-pulse folder, a train folder and a loose reference image."""
    root = tmp_path_factory.mktemp("recordings")
    io = root / "Animal 1" / "Slice 1" / "input output"
    train = root / "Animal 1" / "Slice 1" / "11p at 200uA"
    io.mkdir(parents=True)
    train.mkdir()
    # recorded in the order 100uA, no1, 200uA, 300uA: the last two have no unstimulated recording after them
    make_recording(io / "100uA.tif", 0.2, seed=1, clock="10:00:00")
    make_recording(io / "no1.tif", 0.0, seed=4, clock="10:01:00")
    make_recording(io / "200uA.tif", 0.4, seed=2, clock="10:02:00")
    make_recording(io / "300uA.tif", 0.6, seed=3, clock="10:04:00")
    make_recording(train / "hi1.tif", 0.5, seed=5, clock="11:00:00")
    make_recording(train / "hi1 red.tif", 0.0, seed=6, clock="11:00:30")
    make_recording(train / "no1.tif", 0.0, seed=7, clock="11:01:00")
    tifffile.imwrite(root / "Animal 1" / "Slice 1" / "reference.tif", np.zeros(SHAPE, np.uint16))
    return root


@pytest.fixture(scope="session")
def io_folder(recordings):
    return recordings / "Animal 1" / "Slice 1" / "input output"


@pytest.fixture(scope="session")
def train_folder(recordings):
    return recordings / "Animal 1" / "Slice 1" / "11p at 200uA"
