"""The template every protocol can be built from: a train of pulses, and optionally a recovery pulse.

A template is a few numbers: how many pulses, how far apart, how long their
windows are, whether they share a baseline, which trace is measured, and the
delays of an optional recovery pulse. `build` turns them into a protocol with
regular windows, which can then be fine-tuned. The 2P and 11P protocols are
two fillings of this template (`LIKE`).
"""

from dataclasses import dataclass, field

from ..recordings import FRAME_MS
from .protocol import (
    AS_LISTED,
    BRIGHTNESS,
    EVERY,
    LISTED,
    NO_PARTNER,
    PER_RECORDING,
    PERCENT_SCALE,
    RATIO,
    RATIO_SCALE,
    RECORDED_AFTER,
    Comparison,
    Fit,
    Protocol,
    Pulse,
    PulseTiming,
    Recording,
    Window,
)

END_OF_TRAIN, LAST_PULSE = "end of the train", "last pulse"


@dataclass
class Template:
    name: str = "New protocol"
    frame_ms: float = FRAME_MS
    trace: str = BRIGHTNESS
    partner: str = RECORDED_AFTER
    first_stimulus: int = 103  # frame
    pulses: int = 2
    interval_ms: float = 4000.0
    peak_ms: float = 600.0  # length of each peak window, from its stimulus
    baseline_ms: float = 60.0  # length of each baseline window, ending at its stimulus
    shared_baseline: bool = False
    recovery: bool = False
    recovery_delays_ms: list = field(default_factory=lambda: [500.0, 1000.0, 2500.0, 5000.0])
    recovery_after: str = END_OF_TRAIN  # what the delays are counted from
    stimulated_files: str = "hi{n}.tif"  # {n} is the recording's number, from 1
    unstimulated_files: str = "no{n+1}.tif"  # its unstimulated partner, recorded after it; used with AS_LISTED

    def frames(self, ms):
        return max(round(ms / self.frame_ms), 1)

    def stimuli(self):
        return [round(self.first_stimulus + k * self.interval_ms / self.frame_ms) for k in range(self.pulses)]

    def recovery_stimulus(self, delay_ms):
        """The frame of the recovery pulse after a delay."""
        last = self.first_stimulus + (self.pulses - 1) * self.interval_ms / self.frame_ms
        start = last + (self.interval_ms / self.frame_ms if self.recovery_after == END_OF_TRAIN else 0)
        return round(start + delay_ms / self.frame_ms)

    def file_name(self, pattern, n):
        return pattern.replace("{n+1}", str(n + 1)).replace("{n}", str(n))

    def build(self):
        """The protocol this template describes."""
        partner = RECORDED_AFTER if self.trace == RATIO and self.partner == NO_PARTNER else self.partner
        listed = self.recovery or partner == AS_LISTED
        protocol = Protocol(
            name=self.name,
            sampling_interval_ms=self.frame_ms,
            trace=self.trace,
            partner=partner,
            selection=LISTED if listed else EVERY,
            condition_name="Delay" if self.recovery else "Current",
            condition_unit="ms" if self.recovery else "µA",
            skip_words=["red", "test"],
            windows_follow_condition=self.recovery,
        )
        peak, baseline = self.frames(self.peak_ms), self.frames(self.baseline_ms)
        protocol.place_pulses(self.first_stimulus, self.pulses, self.interval_ms / self.frame_ms, peak, baseline, self.shared_baseline)
        names = [p.name for p in protocol.pulses]
        last = names[-1]

        if self.recovery:
            name = f"P{self.pulses + 1}"
            before = f"BLPre{self.pulses + 1}"
            protocol.baselines[before] = PER_RECORDING
            protocol.pulses.append(Pulse(name, before, per_recording=True))
            for n, delay in enumerate(self.recovery_delays_ms, start=1):
                stimulus = self.recovery_stimulus(delay)
                protocol.recordings.append(Recording(
                    self.file_name(self.stimulated_files, n),
                    self.file_name(self.unstimulated_files, n) if partner == AS_LISTED else "",
                    float(delay),
                    baselines={before: Window(max(stimulus - baseline, 0), stimulus)},
                    pulses={name: PulseTiming(stimulus, Window(stimulus, stimulus + peak))},
                ))
        elif listed:
            for n in range(1, 3):
                protocol.recordings.append(Recording(self.file_name(self.stimulated_files, n),
                                                     self.file_name(self.unstimulated_files, n)))

        if len(names) == 2:
            protocol.comparisons.append(Comparison("PPR", "P2", "P1", RATIO_SCALE))
        elif len(names) > 2:
            protocol.comparisons += [Comparison("P2/P1", "P2", "P1", PERCENT_SCALE), Comparison(f"{last}/P1", last, "P1", PERCENT_SCALE)]
        if self.recovery:
            recovery = protocol.pulses[-1].name
            protocol.comparisons.append(Comparison(f"{recovery}/P1", recovery, "P1", PERCENT_SCALE))
            if last != "P1":
                protocol.comparisons.append(Comparison(f"{recovery}/{last}", recovery, last, PERCENT_SCALE))
        if self.interval_ms >= 1000 or self.pulses == 1:  # room for the response to decay before the next pulse
            protocol.fits.append(Fit("Tau", "P1", 4, self.frames(2000)))
        if protocol.selection == EVERY:
            protocol.summary_statistics = ["min", "max", "mean"]
        return protocol


# The built-in protocols as fillings of the template. Their own windows are tuned by hand; these give the same timing.
LIKE = {
    "2P paired pulse": Template(name="2P paired pulse", pulses=2, interval_ms=4000.0, peak_ms=600.0, baseline_ms=60.0,
                                shared_baseline=False, trace=BRIGHTNESS, partner=RECORDED_AFTER, recovery=False),
    "11P pulse train": Template(name="11P pulse train", pulses=10, interval_ms=100.0, peak_ms=95.0, baseline_ms=85.0,
                                shared_baseline=True, trace=RATIO, partner=AS_LISTED, recovery=True,
                                recovery_delays_ms=[500.0, 1000.0, 2500.0, 5000.0], recovery_after=END_OF_TRAIN),
}
