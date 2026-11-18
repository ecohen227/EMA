"""The built-in protocols, written as code so that their numbers can be checked, and the protocol library.

After changing a built-in protocol, run `python -m ema.evoked.presets` to write
them to `ema/evoked/built_in/` (a test checks that the files match the code).
"""

from pathlib import Path

from ..library import Library, file_name
from ..paths import USER_PROTOCOLS
from ..recordings import FRAME_MS
from .protocol import (
    AS_LISTED,
    BY_CONDITION,
    EVERY,
    LISTED,
    NO_PARTNER,
    RECORDED_AFTER,
    PER_RECORDING,
    PERCENT_SCALE,
    RATIO,
    RATIO_SCALE,
    Comparison,
    Fit,
    Protocol,
    Pulse,
    PulseTiming,
    Recording,
    SliceMean,
    Window,
)

BUILT_IN = Path(__file__).parent / "built_in"
LIBRARY = Library("protocol", Protocol.load, BUILT_IN, USER_PROTOCOLS)


def paired_pulse(corrected=True):
    if corrected:
        name = "2P paired pulse"
        description = (
            "Two pulses 4 s apart. Each stimulated recording is corrected for bleaching with the unstimulated one "
            "recorded right after it. Measured: baselines, dF/F of each pulse, the paired-pulse ratio, the decay "
            "time constant after P1, and per-slice summaries over the currents."
        )
    else:
        name = "2P paired pulse, uncorrected"
        description = (
            "Two pulses 4 s apart, each stimulated recording measured as it is, without an unstimulated partner: for "
            "slices recorded without unstimulated recordings. Otherwise the same as 2P paired pulse."
        )
    return Protocol(
        name=name,
        description=description,
        sampling_interval_ms=FRAME_MS,
        partner=RECORDED_AFTER if corrected else NO_PARTNER,
        selection=EVERY,
        condition_name="Current",
        condition_unit="µA",
        skip_words=["red", "test"],
        baselines={"B1": Window(81, 93), "B2": Window(904, 925)},
        pulses=[
            Pulse("P1", "B1", Window(83, 205), stimulus=103),
            Pulse("P2", "B2", Window(904, 1125), stimulus=928),
        ],
        comparisons=[Comparison("PPR", "P2", "P1", RATIO_SCALE)],
        fits=[Fit("Tau", "P1", 4, 412)],
        summary_statistics=["min", "max", "mean"],
        summary_means=[SliceMean("100-400", BY_CONDITION, 100.0, 400.0)],
        summary_baseline_spread=True,
    )


TRAIN_PEAKS = [(105, 124), (125, 144), (145, 164), (165, 185), (186, 200), (201, 226), (227, 247), (248, 267), (268, 288), (289, 310)]
# file, unstimulated partner, delay (ms) from the end of the train, recovery stimulus, BLPre11, P11.
# The stimulus frames are worked out from the protocol (see template.py); the windows are the hand-tuned ones.
RECOVERY = [
    ("hi1.tif", "no2.tif", 500, 412, (401, 413), (413, 443)),
    ("hi2.tif", "no3.tif", 1000, 515, (504, 515), (516, 541)),
    ("hi3.tif", "no4.tif", 2500, 825, (814, 825), (825, 847)),
    ("hi4.tif", "no5.tif", 5000, 1340, (1331, 1341), (1342, 1367)),
]


def pulse_train():
    train = [
        Pulse(f"P{i}", "BL", Window(*peak), stimulus=103 + round((i - 1) * 100 / FRAME_MS))
        for i, peak in enumerate(TRAIN_PEAKS, start=1)
    ]
    recovery = Pulse("P11", "BLPre11", per_recording=True)
    recordings = [
        Recording(
            file,
            unstimulated,
            float(delay),
            baselines={"BLPre11": Window(*baseline)},
            pulses={"P11": PulseTiming(stimulus, Window(*peak))},
        )
        for file, unstimulated, delay, stimulus, baseline, peak in RECOVERY
    ]
    comparisons = [
        Comparison("P2/P1", "P2", "P1", PERCENT_SCALE),
        Comparison("P10/P1", "P10", "P1", PERCENT_SCALE),
        Comparison("P11/P1", "P11", "P1", PERCENT_SCALE),
        Comparison("P11/P10", "P11", "P10", PERCENT_SCALE),
    ] + [Comparison(f"nP{i}/BL", f"P{i}", "P1", RATIO_SCALE) for i in range(1, 11)]
    return Protocol(
        name="11P pulse train",
        description=(
            "Ten pulses at 10 Hz and a recovery pulse after 0.5 to 5 s. Each stimulated recording is divided by "
            "the unstimulated one recorded after it; responses are rises above the baseline before the train."
        ),
        sampling_interval_ms=FRAME_MS,
        trace=RATIO,
        partner=AS_LISTED,
        selection=LISTED,
        condition_name="Delay",
        condition_unit="ms",
        skip_words=[],
        windows_follow_condition=True,
        recordings=recordings,
        baselines={"BL": Window(83, 101), "BLPre11": PER_RECORDING},
        pulses=train + [recovery],
        comparisons=comparisons,
    )


def paired_pulse_uncorrected():
    return paired_pulse(corrected=False)


PRESETS = [paired_pulse, paired_pulse_uncorrected, pulse_train]


def write_presets():
    BUILT_IN.mkdir(exist_ok=True)
    for make in PRESETS:
        protocol = make()
        assert not protocol.problems(), protocol.problems()
        protocol.save(BUILT_IN / file_name(protocol.name))
        print("wrote", file_name(protocol.name))


if __name__ == "__main__":
    write_presets()
