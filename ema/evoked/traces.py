"""The trace (or movie) a protocol measures, made from a stimulated recording and its unstimulated partner.

Three cases:

- brightness, no partner: the stimulated recording as it is;
- brightness with a partner: the stimulated recording corrected for bleaching,
  stimulated × mean(partner over the correction window) ÷ partner. It stays in
  the stimulated recording's brightness units, so dF/F keeps its meaning;
- stimulated ÷ unstimulated in %: (stimulated ÷ partner − 1) × 100.

The correction window is the first baseline window of the protocol. Its factor,
mean(partner over it), is the same for a pulse's peak and its baseline, so it
cancels in every response (peak ÷ baseline) and only sets the scale of the
baselines and peaks themselves.
"""

import numpy as np

from ..recordings import recorded_after
from .protocol import AS_LISTED, RATIO


def find_partner(protocol, path, paths, recording=None, times=None):
    """The unstimulated partner of the stimulated recording `path` among the recordings `paths` of its folder.

    Returns (partner, reason): the partner's path, or None and why there is
    none. The partner is None with no reason when the protocol needs none. A
    listed recording that names a partner always uses it. `times` caches the
    time stamps of the files, by path.
    """
    if not protocol.uses_partner:
        return None, ""
    named = recording.unstimulated.strip() if recording is not None else ""
    if named:
        match = next((other for other in paths if other.name.lower() == named.lower()), None)
        return (match, "") if match else (None, f"{named} is not in this folder.")
    if protocol.partner == AS_LISTED:
        return None, f"{path.name} has no unstimulated partner in the list."
    return recorded_after(path, protocol.unstimulated_files(paths), times)


def correction_window(protocol, recording=None):
    """The window the partner is scaled to: the protocol's first baseline window."""
    first = next(iter(protocol.baselines), None)
    return protocol.baseline_window(first, recording) if first is not None else None


def make_trace(protocol, stimulated, partner=None, recording=None):
    """The measured trace, or movie with frames first, from the stimulated signal and its partner's (if any)."""
    if protocol.uses_partner and partner is None:
        raise ValueError("This protocol needs an unstimulated partner for each recording.")
    if not protocol.uses_partner:
        return stimulated
    window = None if protocol.trace == RATIO else correction_window(protocol, recording)
    return combine(stimulated, partner, protocol.trace == RATIO, window)


def make_movie(protocol, stimulated, partner=None, recording=None):
    """The signal of every pixel the protocol measures, made like the trace but pixel by pixel (float32, frames first).

    The partner is clamped to at least 1 count, so a dark pixel never divides by 0.
    """
    movie = stimulated.astype(np.float32)
    if partner is None:
        return movie
    window = None if protocol.trace == RATIO else correction_window(protocol, recording)
    return combine(movie, np.maximum(partner.astype(np.float32), 1), protocol.trace == RATIO, window)


def combine(stimulated, partner, ratio, window=None):
    """Stimulated ÷ partner in % (`ratio`), or the stimulated signal corrected for bleaching by the partner."""
    if partner.shape != stimulated.shape:
        raise ValueError("The stimulated and the unstimulated recording have different numbers of frames.")
    if ratio:
        return (stimulated / partner - 1) * 100
    if window is None:
        raise ValueError("The correction by the unstimulated partner needs a baseline window.")
    return stimulated * (partner[window.start : window.end].mean(axis=0) / partner)
