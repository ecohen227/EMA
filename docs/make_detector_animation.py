"""The animation of the detector on a busy recording (a slice in 4-AP), for "How the detector works".

    python docs/make_detector_animation.py <recording.tif>

Searches the recording with the Standard detector and writes
docs/figures/detector_4ap.gif: the dF/F movie at half speed, with each event
circled from its onset for half a second. The electrode is found on the
recording's own resting image. The recording is only read.
"""

import sys
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import ndimage  # noqa: E402

from ema.recordings import load_stack  # noqa: E402
from ema.roi_selection import RoiSettings, find_electrode  # noqa: E402
from ema.spontaneous.detection import detect, resting_brightness  # noqa: E402
from ema.spontaneous.settings import DetectorSettings  # noqa: E402

FIGURES = Path(__file__).parent / "figures"
PER_PICTURE = 8  # frames averaged into one picture: 8 × 4.849 ms ≈ 39 ms
PICTURE_MS = 80  # how long each picture is shown: half speed
SHOWN_MS = 500  # how long a circle stays after its onset
DISPLAY_BLUR_UM = 48.0  # for display only; the search does not use it
LIMITS = (0.0, 5.0)  # % dF/F


def main():
    path = Path(sys.argv[1])
    stack = load_stack(path)
    s = DetectorSettings()
    f0 = resting_brightness(stack, s)
    middle = (f0.shape[1] // 2, f0.shape[0] // 2)
    electrode = find_electrode(f0, middle, replace(RoiSettings(), electrode_max_distance_px=max(f0.shape)))
    found = detect(stack, electrode, s)
    print(f"{len(found.events)} events; sign-flipped {len(found.sign_flipped)}, time-reversed {len(found.time_reversed)}")

    d = found.dff
    d = d - np.median(d[:, found.tissue], axis=1)[:, None, None]
    d = ndimage.gaussian_filter(d, (0, s.pixels(DISPLAY_BLUR_UM), s.pixels(DISPLAY_BLUR_UM))) * 100
    pictures = len(d) // PER_PICTURE
    movie = d[: pictures * PER_PICTURE].reshape(pictures, PER_PICTURE, *d.shape[1:]).mean(1)
    movie[:, ~found.tissue] = np.nan
    onsets = (found.events[:, 0] - found.first_frame) / PER_PICTURE  # in pictures
    stays = SHOWN_MS / (s.frame_ms * PER_PICTURE)

    figure, axis = plt.subplots(figsize=(4.4, 4.9), dpi=90)
    figure.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.1)
    axis.set_facecolor("#3a3a3a")
    shown = axis.imshow(movie[0], cmap="inferno", vmin=LIMITS[0], vmax=LIMITS[1], interpolation="bilinear")
    axis.set(xticks=[], yticks=[])
    axis.set_title("A slice in 4-AP, at half speed\ndF/F 0–5 %; events found, circled", fontsize=10)
    clock = figure.text(0.5, 0.035, "", ha="center", fontsize=10)
    circles = []
    frames = []
    for n in range(pictures):
        shown.set_data(movie[n])
        for circle in circles:
            circle.remove()
        circles = []
        for onset, (_, row, col, _) in zip(onsets, found.events):
            if onset <= n < onset + stays:
                circles.append(axis.add_patch(Circle((col, row), s.pixels(s.blur_um), fill=False, color="cyan", lw=1.6)))
        seconds = (found.first_frame + n * PER_PICTURE) * s.frame_ms / 1000
        clock.set_text(f"{seconds:4.1f} s     events so far: {int((onsets <= n).sum())}")
        figure.canvas.draw()
        frames.append(np.asarray(figure.canvas.buffer_rgba())[..., :3].copy())
    plt.close(figure)

    palette = Image.fromarray(np.concatenate(frames[:: max(1, pictures // 12)], axis=0)).quantize(colors=96)
    images = [Image.fromarray(frame).quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    target = FIGURES / "detector_4ap.gif"
    images[0].save(target, save_all=True, append_images=images[1:], duration=PICTURE_MS, loop=0, optimize=True)
    print(f"saved {target.name}: {pictures} pictures, {target.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
