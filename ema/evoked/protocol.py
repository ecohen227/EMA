"""A protocol: everything the evoked analysis needs to know to measure a recording.

A protocol says

- which trace is measured: the brightness of the ROI, or a stimulated
  recording divided by its unstimulated partner;
- how each stimulated recording finds its unstimulated partner: the one
  recorded right after it, the one named in a list, or none;
- which recordings of a folder are measured;
- the windows of every pulse: a baseline window (its mean) and a peak window
  (its maximum);
- what is derived from them: comparisons of two responses, exponential fits,
  measures of the response shape and of its spread over the slice, and
  summaries over a slice, including curves fitted across its recordings;
- which slices are left out of the tables (exclusions), and whether the peak
  of each pulse is written besides its response.

Times are frames: windows are [start, end) and frame 0 is the second frame of
the TIFF, because the first is dropped when a recording is read. Nothing here
needs the GUI.
"""

import json
import re
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path

from ..recordings import FRAME_MS, has_skip_word, is_no_stim
from .catalogue import KINETIC, KINETIC_KEYS, NEAR_TO_FAR, SPATIAL, SPATIAL_KEYS, SpatialSettings

FORMAT = "EMA evoked protocol"
FORMAT_VERSION = 1

BRIGHTNESS = "brightness"
RATIO = "ratio to unstimulated"
TRACES = (BRIGHTNESS, RATIO)

# How a stimulated recording finds its unstimulated partner
RECORDED_AFTER = "recorded right after"  # by the time stamps in the files; the one right before if none was after
AS_LISTED = "as listed"  # each listed recording names its partner
NO_PARTNER = "none"  # brightness only: measured as it is, not corrected for bleaching
PARTNERS = (RECORDED_AFTER, AS_LISTED, NO_PARTNER)

EVERY = "every stimulated recording"
LISTED = "listed recordings"
SELECTIONS = (EVERY, LISTED)

PER_RECORDING = "per recording"

RATIO_SCALE, PERCENT_SCALE = "ratio", "percent"
SCALES = (RATIO_SCALE, PERCENT_SCALE)

SINGLE, DOUBLE = "single", "double"
FIT_KINDS = (SINGLE, DOUBLE)

RECOVERY, SATURATION = "recovery", "saturation"
CONDITION_MODELS = (RECOVERY, SATURATION)
STATISTICS = ("min", "max", "mean")

# Which recordings a mean over recordings or an exclusion takes: those in a condition range, those with certain
# file names, or (an exclusion only) all
BY_CONDITION, BY_FILES, ALL_RECORDINGS = "condition", "files", "all"

# Exclusions. The one value an exclusion makes from the recordings of a slice:
SPREAD_OF_LARGEST, SPREAD_OF_SMALLEST, RANGE = "spread of largest", "spread of smallest", "range"
VARIATION, MEAN, MEDIAN, SMALLEST, LARGEST = "coefficient of variation", "mean", "median", "smallest", "largest"
SLICE_VALUES = {  # name -> (formula over the values of the slice's recordings, least number of recordings it needs)
    SPREAD_OF_LARGEST: ("(largest − smallest) ÷ largest × 100", 2),
    SPREAD_OF_SMALLEST: ("(largest − smallest) ÷ smallest × 100", 2),
    RANGE: ("largest − smallest", 2),
    VARIATION: ("standard deviation ÷ mean × 100", 2),
    MEAN: ("mean", 1),
    MEDIAN: ("median", 1),
    SMALLEST: ("smallest", 1),
    LARGEST: ("largest", 1),
}
IN_PERCENT = (SPREAD_OF_LARGEST, SPREAD_OF_SMALLEST, VARIATION)
# How it decides which slices are unusual: by the slices' quartiles or mean, or by a fixed limit
INTERQUARTILE, DEVIATIONS, ABOVE, BELOW = "interquartile", "standard deviations", "above", "below"
EXCLUSION_TESTS = (INTERQUARTILE, DEVIATIONS, ABOVE, BELOW)
EITHER_SIDE, HIGH_SIDE, LOW_SIDE = "either", "high", "low"
SIDES = (EITHER_SIDE, HIGH_SIDE, LOW_SIDE)
# Which slices the quartiles or the mean are taken over
AMONG_ALL, AMONG_GROUP = "all slices", "its group"
AMONGS = (AMONG_ALL, AMONG_GROUP)


class ProtocolError(ValueError):
    pass


@dataclass
class Window:
    """Frames [start, end)."""

    start: int
    end: int

    def to_list(self):
        return [self.start, self.end]

    def text(self):
        return f"frames {self.start} to {self.end - 1}"


@dataclass
class Pulse:
    """One stimulation: the frame it happens at, its peak window and the baseline it is measured from.

    A pulse whose timing differs between recordings (such as a recovery pulse
    after different delays) is `per_recording`: its stimulus and peak window
    are then given for each listed recording.
    """

    name: str
    baseline: str
    peak: Window = None
    stimulus: int = None
    per_recording: bool = False


@dataclass
class PulseTiming:
    """The stimulus and peak window of a per-recording pulse in one recording."""

    stimulus: int = None
    peak: Window = None


@dataclass
class Recording:
    """One listed recording: its file, its unstimulated partner, its condition and its own timing."""

    file: str
    unstimulated: str = ""
    condition: float = None
    baselines: dict = field(default_factory=dict)  # name -> Window, for per-recording baselines
    pulses: dict = field(default_factory=dict)  # name -> PulseTiming, for per-recording pulses


@dataclass
class Comparison:
    """The response of `pulse` divided by the response of `relative_to`, as a ratio or in percent."""

    name: str
    pulse: str
    relative_to: str
    scale: str = RATIO_SCALE


@dataclass
class Fit:
    """An exponential decay fitted to the trace over `length` frames.

    A single fit is A·exp(−t/τ) + C. A double fit is
    A1·exp(−t/τ1) + A2·exp(−t/τ2) + C, with τ1 the faster time constant.
    The fit starts `start` frames after the maximum of the peak window of the
    pulse named in `after`, or at frame `start` when `after` is None.
    """

    name: str
    after: str = None
    start: int = 4
    length: int = 412
    kind: str = SINGLE

    def measure_names(self):
        if self.kind == DOUBLE:
            return [f"{self.name} fast", f"{self.name} slow", f"{self.name} fast fraction"]
        return [self.name]


@dataclass
class ConditionFit:
    """A curve fitted, per slice, to a per-recording measure against the condition of the slice's recordings.

    recovery: y = plateau − (plateau − start)·exp(−x/τ), with the plateau fitted or fixed;
    saturation: y = top·xⁿ ÷ (halfⁿ + xⁿ), a Hill curve, for an input–output relation.
    """

    name: str
    measure: str
    model: str = RECOVERY
    plateau: float = None  # recovery only: the value it is fixed at, or None to fit it

    def measure_names(self):
        if self.model == SATURATION:
            return [f"{self.name} half-max", f"{self.name} max", f"{self.name} steepness"]
        return [f"{self.name} time constant", f"{self.name} start"] + ([f"{self.name} plateau"] if self.plateau is None else [])


@dataclass
class SliceMean:
    """A mean, per slice, over some of its recordings: those with a condition from `low` to `high`, or those whose
    file name matches one of the patterns in `files` (with or without .tif, upper and lower case alike; * stands for
    any characters, ? for one)."""

    name: str  # its columns are "<measure> mean <name>"
    by: str = BY_CONDITION
    low: float = 100.0
    high: float = 400.0
    files: list = field(default_factory=list)  # such as ["hi*"] or ["hi1", "hi2", "hi3", "hi4"]

    def includes(self, file_name, condition):
        return _chosen(self.by, file_name, condition, self.low, self.high, self.files)

    def automatic_name(self):
        """The name it has until it is given another: '100-400', or the file names without wildcards ('hi')."""
        if self.by == BY_FILES:
            return "+".join(re.sub(r"\.tiff?$|[*?\[\]]", "", pattern, flags=re.IGNORECASE) for pattern in self.files)
        return f"{self.low:g}-{self.high:g}"

    def which(self, condition):
        """The recordings it takes, in words, such as 'with a Current (µA) from 100 to 400'."""
        if self.by == BY_FILES:
            return f"whose file name matches {', '.join(self.files)}"
        return f"with a {condition} from {self.low:g} to {self.high:g}"


def _chosen(by, file_name, condition, low, high, files):
    """Whether a recording is one of those chosen by a condition range, by file-name patterns, or (ALL_RECORDINGS) all."""
    if by == BY_FILES:
        name = file_name.lower()
        return any(fnmatchcase(name, pattern.lower()) or fnmatchcase(Path(name).stem, pattern.lower()) for pattern in files)
    if by == BY_CONDITION:
        return condition is not None and low <= condition <= high
    return True


@dataclass
class Exclusion:
    """Leaves a slice out of both tables when one value made from its recordings is unusual among the slices.

    The value combines one per-recording measure over the slice's recordings
    (all, or those in a condition range, or with certain file names), such
    as the spread of B1: (largest B1 − smallest B1) ÷ largest B1 × 100. The
    slice is left out when that value is outside Q1 − k·IQR to Q3 + k·IQR of
    the slices (INTERQUARTILE, k = `factor`), more than k standard deviations
    from their mean (DEVIATIONS), or above or below `limit`. With `side`,
    only unusually high or only unusually low values count. The slices are
    all slices, or (AMONG_GROUP) those of the slice's group.
    """

    measure: str
    statistic: str = SPREAD_OF_LARGEST
    by: str = ALL_RECORDINGS
    low: float = 100.0
    high: float = 400.0
    files: list = field(default_factory=list)
    test: str = INTERQUARTILE
    factor: float = 1.5
    limit: float = 0.0
    side: str = EITHER_SIDE
    among: str = AMONG_ALL

    def includes(self, file_name, condition):
        return _chosen(self.by, file_name, condition, self.low, self.high, self.files)

    def unit(self, measure_unit):
        """The unit of the slice's value, given the unit of the measure."""
        return "%" if self.statistic in IN_PERCENT else measure_unit

    @property
    def relative(self):
        """True when it compares a slice with the other slices; False for a fixed limit."""
        return self.test in (INTERQUARTILE, DEVIATIONS)

    def value_text(self, condition_label=""):
        """The slice's value in words, such as 'B1: (largest − smallest) ÷ largest × 100 over its recordings'."""
        formula = SLICE_VALUES[self.statistic][0]
        which = {BY_FILES: f" whose file name matches {', '.join(self.files)}",
                 BY_CONDITION: f" with a {condition_label or 'condition'} from {self.low:g} to {self.high:g}"}.get(self.by, "")
        return f"{self.measure}: {formula} over its recordings{which}"

    def test_text(self, unit=""):
        """When a slice is left out, in words, such as 'above Q3 + 1.5 × IQR of all slices'."""
        among = "of all slices" if self.among == AMONG_ALL else "of the slices of its group"
        k = f"{self.factor:g}"
        if self.test == INTERQUARTILE:
            limits = {EITHER_SIDE: f"below Q1 − {k} × IQR or above Q3 + {k} × IQR", HIGH_SIDE: f"above Q3 + {k} × IQR",
                      LOW_SIDE: f"below Q1 − {k} × IQR"}[self.side]
            return f"{limits} {among} (Q1 and Q3 are the quartiles, IQR = Q3 − Q1)"
        if self.test == DEVIATIONS:
            where = {EITHER_SIDE: "from", HIGH_SIDE: "above", LOW_SIDE: "below"}[self.side]
            return f"more than {k} standard deviations {where} the mean {among}"
        return f"{self.test} {self.limit:g}{' ' + unit if unit and unit != 'ratio' else ''}"


def file_patterns(text):
    """File-name patterns from a text such as 'hi1, hi2' (or a list of them): stripped, the empty ones left out."""
    parts = text.split(",") if isinstance(text, str) else text
    return [str(part).strip() for part in parts if str(part).strip()]


@dataclass
class Column:
    """One number the analysis will produce: per recording, or per slice (a summary of the recordings)."""

    name: str
    unit: str
    explanation: str
    per: str = "recording"


@dataclass
class Protocol:
    name: str
    description: str = ""
    sampling_interval_ms: float = FRAME_MS
    trace: str = BRIGHTNESS
    partner: str = RECORDED_AFTER
    selection: str = EVERY
    condition_name: str = "Current"
    condition_unit: str = "µA"
    skip_words: list = field(default_factory=lambda: ["red"])
    recordings: list = field(default_factory=list)  # Recording, for LISTED
    baselines: dict = field(default_factory=dict)  # name -> Window, or PER_RECORDING
    pulses: list = field(default_factory=list)
    comparisons: list = field(default_factory=list)
    fits: list = field(default_factory=list)
    windows_follow_condition: bool = False  # per-recording windows move when a recording's delay is changed
    kinetic_measures: list = field(default_factory=list)  # keys of catalogue.KINETIC
    kinetic_pulses: list = None  # the pulses they are measured on; None means every pulse
    kinetic_smoothing_frames: int = 3
    spatial_measures: list = field(default_factory=list)  # keys of catalogue.SPATIAL
    spatial_pulses: list = field(default_factory=lambda: ["P1"])
    near_to_far: list = field(default_factory=list)  # names of comparisons also measured as near-to-far indices
    spatial: SpatialSettings = field(default_factory=SpatialSettings)
    slice_file: bool = True  # write Evoked per slice.xlsx
    write_peaks: bool = False  # write each pulse's peak (the maximum of the trace) besides its response
    exclusions: list = field(default_factory=list)  # Exclusion: slices left out of both tables
    summary_statistics: list = field(default_factory=list)
    summary_means: list = field(default_factory=list)  # SliceMean
    summary_baseline_spread: bool = False
    condition_fits: list = field(default_factory=list)  # ConditionFit

    # ------------------------------------------------------------------
    # Looking things up
    # ------------------------------------------------------------------

    @property
    def trace_unit(self):
        return "counts" if self.trace == BRIGHTNESS else "%"

    def pulse(self, name):
        return next((pulse for pulse in self.pulses if pulse.name == name), None)

    def baseline_window(self, name, recording=None):
        """The baseline window `name` in a recording. None if it is not known (yet)."""
        window = self.baselines.get(name)
        if window == PER_RECORDING:
            return recording.baselines.get(name) if recording else None
        return window

    def pulse_timing(self, pulse, recording=None):
        """(stimulus frame, peak window) of a pulse in a recording. Either can be None if it is not known."""
        if not pulse.per_recording:
            return pulse.stimulus, pulse.peak
        timing = recording.pulses.get(pulse.name) if recording else None
        return (timing.stimulus, timing.peak) if timing else (None, None)

    def per_recording_baselines(self):
        return [name for name, window in self.baselines.items() if window == PER_RECORDING]

    def per_recording_pulses(self):
        return [pulse.name for pulse in self.pulses if pulse.per_recording]

    def measured_files(self, paths):
        """The recordings of a folder that are measured with EVERY: all stimulated ones but the skipped."""
        return [path for path in paths if not is_no_stim(path) and not self.skipped(path)]

    def unstimulated_files(self, paths):
        """The recordings of a folder that can be an unstimulated partner: named 'no' and a number, not skipped."""
        return [path for path in paths if is_no_stim(path) and not self.skipped(path)]

    def skipped(self, path):
        return has_skip_word(path, self.skip_words)

    @property
    def uses_partner(self):
        return self.trace == RATIO or self.partner != NO_PARTNER

    def condition_of(self, file_name, recording=None):
        """A recording's condition: the one in the list, or else the number its file name starts with (300uA.tif: 300)."""
        if recording is not None:
            return recording.condition
        number = re.match(r"\d+(\.\d+)?", file_name)
        return float(number.group()) if number else None

    @property
    def condition_label(self):
        """The condition's name with its unit, such as 'Current (µA)'."""
        return f"{self.condition_name} ({self.condition_unit})" if self.condition_unit else self.condition_name

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def set_baseline_window(self, name, window, recording=None):
        """Change a baseline window; a per-recording one is changed in `recording`."""
        if self.baselines[name] == PER_RECORDING:
            recording.baselines[name] = window
        else:
            self.baselines[name] = window

    def set_pulse_timing(self, pulse, recording=None, stimulus=..., peak=...):
        """Change the stimulus and/or peak window of a pulse; a per-recording one is changed in `recording`."""
        target = pulse
        if pulse.per_recording:
            target = recording.pulses.setdefault(pulse.name, PulseTiming())
        if stimulus is not ...:
            target.stimulus = stimulus
        if peak is not ...:
            target.peak = peak

    def set_baseline_per_recording(self, name, on):
        """Give a baseline window its own timing in every listed recording, or one timing for all."""
        window = self.baselines[name]
        if on and window != PER_RECORDING:
            for recording in self.recordings:
                recording.baselines[name] = Window(window.start, window.end)
            self.baselines[name] = PER_RECORDING
        elif not on and window == PER_RECORDING:
            first = next((r.baselines[name] for r in self.recordings if r.baselines.get(name)), Window(0, 10))
            for recording in self.recordings:
                recording.baselines.pop(name, None)
            self.baselines[name] = Window(first.start, first.end)

    def set_pulse_per_recording(self, pulse, on):
        """Give a pulse its own stimulus and peak window in every listed recording, or one for all."""
        if on and not pulse.per_recording:
            for recording in self.recordings:
                peak = Window(pulse.peak.start, pulse.peak.end) if pulse.peak else None
                recording.pulses[pulse.name] = PulseTiming(pulse.stimulus, peak)
            pulse.per_recording, pulse.stimulus, pulse.peak = True, None, None
        elif not on and pulse.per_recording:
            first = next((r.pulses[pulse.name] for r in self.recordings if r.pulses.get(pulse.name)), PulseTiming())
            for recording in self.recordings:
                recording.pulses.pop(pulse.name, None)
            pulse.per_recording, pulse.stimulus = False, first.stimulus
            pulse.peak = Window(first.peak.start, first.peak.end) if first.peak else Window(0, 10)

    def set_condition(self, recording, value):
        """Change a listed recording's condition. With `windows_follow_condition`, its per-recording windows and
        stimuli move by the change, read as a delay in ms."""
        if self.windows_follow_condition and recording.condition is not None and value is not None:
            shift = round((value - recording.condition) / self.sampling_interval_ms)
            for name, window in recording.baselines.items():
                recording.baselines[name] = Window(max(window.start + shift, 0), max(window.end + shift, 1))
            for timing in recording.pulses.values():
                if timing.stimulus is not None:
                    timing.stimulus = max(timing.stimulus + shift, 0)
                if timing.peak is not None:
                    timing.peak = Window(max(timing.peak.start + shift, 0), max(timing.peak.end + shift, 1))
        recording.condition = value

    def rename(self, old, new):
        """Rename a baseline, pulse, comparison or fit, and everything that refers to it."""
        if old in self.baselines:
            self.baselines = {new if name == old else name: window for name, window in self.baselines.items()}
            for pulse in self.pulses:
                pulse.baseline = new if pulse.baseline == old else pulse.baseline
            for recording in self.recordings:
                if old in recording.baselines:
                    recording.baselines[new] = recording.baselines.pop(old)
        for pulse in self.pulses:
            if pulse.name == old:
                pulse.name = new
                for recording in self.recordings:
                    if old in recording.pulses:
                        recording.pulses[new] = recording.pulses.pop(old)
        for comparison in self.comparisons:
            comparison.pulse = new if comparison.pulse == old else comparison.pulse
            comparison.relative_to = new if comparison.relative_to == old else comparison.relative_to
            comparison.name = new if comparison.name == old else comparison.name
        for fit in self.fits:
            fit.after = new if fit.after == old else fit.after
            fit.name = new if fit.name == old else fit.name
        for fit in self.condition_fits:
            fit.name = new if fit.name == old else fit.name
            if fit.measure == old or fit.measure.startswith(old + " "):
                fit.measure = new + fit.measure[len(old):]
        for exclusion in self.exclusions:
            if exclusion.measure == old or exclusion.measure.startswith(old + " "):
                exclusion.measure = new + exclusion.measure[len(old):]
        if self.kinetic_pulses is not None:
            self.kinetic_pulses = [new if n == old else n for n in self.kinetic_pulses]
        self.spatial_pulses = [new if n == old else n for n in self.spatial_pulses]
        self.near_to_far = [new if n == old else n for n in self.near_to_far]

    def names(self):
        """Every name the user gives: windows, pulses, comparisons and fits (each must be unique)."""
        names = list(self.baselines) + [p.name for p in self.pulses] + [c.name for c in self.comparisons]
        return names + [name for fit in self.fits for name in fit.measure_names()] + [f.name for f in self.condition_fits]

    def new_name(self, prefix):
        """The first free name prefix1, prefix2, …"""
        taken = set(self.names())
        number = 1
        while f"{prefix}{number}" in taken:
            number += 1
        return f"{prefix}{number}"

    def add_pulse(self):
        """A new pulse one inter-pulse interval after the last one.

        It keeps the last pulse's timing relative to its stimulus. When every
        pulse has a baseline of its own, the new pulse gets one too, moved by
        the same interval; otherwise it shares the last pulse's baseline.
        """
        fixed = [p for p in self.pulses if not p.per_recording and p.peak]
        if not fixed:
            baseline = next((n for n, w in self.baselines.items() if w != PER_RECORDING), None) or self.add_baseline()
            pulse = Pulse(self.new_name("P"), baseline, Window(100, 200), 100)
            self.pulses.append(pulse)
            return pulse
        last = fixed[-1]
        if len(fixed) >= 2 and last.stimulus is not None and fixed[-2].stimulus is not None:
            step = last.stimulus - fixed[-2].stimulus
        elif len(fixed) >= 2:
            step = last.peak.start - fixed[-2].peak.start
        else:
            step = 2 * (last.peak.end - last.peak.start)
        baseline = last.baseline
        own_baselines = len({p.baseline for p in fixed}) == len(fixed)
        window = self.baselines.get(baseline)
        if own_baselines and isinstance(window, Window):
            baseline = self.new_name("B")
            self.baselines[baseline] = Window(window.start + step, window.end + step)
        stimulus = None if last.stimulus is None else last.stimulus + step
        pulse = Pulse(self.new_name("P"), baseline, Window(last.peak.start + step, last.peak.end + step), stimulus)
        self.pulses.append(pulse)
        return pulse

    def add_baseline(self):
        name = self.new_name("B")
        self.baselines[name] = Window(80, 100)
        return name

    def place_pulses(self, first_stimulus, count, interval_frames, peak_frames, baseline_frames, shared_baseline):
        """Replace every pulse and baseline that has one timing for all recordings by a regular train.

        Pulse k (from 1) is stimulated at first_stimulus + (k − 1) · interval. Its
        peak window starts at its stimulus and lasts `peak_frames`. Its baseline
        ends at its stimulus and lasts `baseline_frames`; with `shared_baseline`
        all pulses use the one before the first pulse.
        """
        kept_pulses = [p for p in self.pulses if p.per_recording]
        kept_baselines = {n: w for n, w in self.baselines.items() if w == PER_RECORDING}
        self.pulses, self.baselines = [], {}
        for k in range(count):
            stimulus = round(first_stimulus + k * interval_frames)
            name = "BL" if shared_baseline else f"B{k + 1}"
            if not shared_baseline or k == 0:
                self.baselines[name] = Window(max(stimulus - baseline_frames, 0), stimulus)
            self.pulses.append(Pulse(f"P{k + 1}", name, Window(stimulus, stimulus + peak_frames), stimulus))
        self.baselines.update(kept_baselines)
        for pulse in kept_pulses:
            if pulse.name in {p.name for p in self.pulses}:  # a per-recording pulse keeps a name of its own
                new = self.new_name("P")
                for recording in self.recordings:
                    if pulse.name in recording.pulses:
                        recording.pulses[new] = recording.pulses.pop(pulse.name)
                pulse.name = new
            self.pulses.append(pulse)

    # ------------------------------------------------------------------
    # What will be measured
    # ------------------------------------------------------------------

    def measures(self):
        """Every number the analysis will write, in order: per recording first, then per slice."""
        per_recording = self.recording_measures(self.write_peaks)
        return per_recording + self._slice_measures(per_recording, self.recording_measures())

    def recording_measures(self, peaks=True):
        """Every number measured per recording, in order. The peaks of the pulses are always measured (the
        responses are made from them), but only written with `write_peaks`; `peaks` False leaves them out."""
        per_recording = []
        for name, window in self.baselines.items():
            where = "set for each recording" if window == PER_RECORDING else window.text()
            per_recording.append(Column(name, self.trace_unit, f"Mean of the trace over the baseline window ({where})."))

        for pulse in self.pulses:
            where = "set for each recording" if pulse.per_recording else pulse.peak.text() if pulse.peak else "not set"
            if peaks:
                per_recording.append(Column(f"{pulse.name} peak", self.trace_unit,
                                            f"Maximum of the trace over the peak window ({where})."))
            per_recording.append(Column(f"{pulse.name} response", "%", self.response_explanation(pulse)))

        for metric, pulse in self._chosen(KINETIC, self.kinetic_measures, self.kinetic_pulse_names()):
            per_recording.append(Column(f"{pulse} {metric.key}", metric.unit, metric.explanation.format(pulse=pulse)))
        for metric, pulse in self._chosen(SPATIAL, self.spatial_measures, self.spatial_pulses):
            per_recording.append(Column(f"{pulse} {metric.key}", metric.unit, metric.explanation.format(pulse=pulse)))

        for comparison in self.comparisons:
            times = " × 100" if comparison.scale == PERCENT_SCALE else ""
            per_recording.append(
                Column(
                    comparison.name,
                    "%" if comparison.scale == PERCENT_SCALE else "ratio",
                    f"{comparison.pulse} response ÷ {comparison.relative_to} response{times}.",
                )
            )
            if comparison.name in self.near_to_far:
                per_recording.append(Column(f"{comparison.name} near-to-far", NEAR_TO_FAR.unit,
                                             NEAR_TO_FAR.explanation.format(pulse=comparison.name)))

        for fit in self.fits:
            start = f"{fit.start} frames after the maximum of {fit.after}" if fit.after else f"at frame {fit.start}"
            duration = fit.length * self.sampling_interval_ms / 1000
            where = f"fitted to the trace, starting {start}, for {fit.length} frames ({duration:.2f} s)"
            if fit.kind == DOUBLE:
                formula = "A1·exp(−t/τ1) + A2·exp(−t/τ2) + C"
                described = [("ms", f"The faster time constant τ1 of {formula} {where}."),
                             ("ms", f"The slower time constant τ2 of {formula} {where}."),
                             ("fraction", f"A1 ÷ (A1 + A2): the share of the fast decay in {formula} {where}.")]
            else:
                described = [("ms", f"Time constant τ of A·exp(−t/τ) + C {where}.")]
            per_recording += [Column(name, unit, text) for name, (unit, text) in zip(fit.measure_names(), described)]
        return per_recording

    def kinetic_pulse_names(self):
        names = [p.name for p in self.pulses]
        return names if self.kinetic_pulses is None else [n for n in names if n in self.kinetic_pulses]

    @staticmethod
    def _chosen(catalogue, keys, pulses):
        """(metric, pulse name) of every chosen measure, per pulse in catalogue order."""
        return [(metric, pulse) for pulse in pulses for metric in catalogue if metric.key in keys]

    def trace_explanation(self):
        """What the measured trace is, in one or two sentences."""
        found = {
            RECORDED_AFTER: "the unstimulated recording made right after it (or, if none was, right before it)",
            AS_LISTED: "the unstimulated recording listed with it",
        }.get(self.partner, "")
        if self.trace == RATIO:
            return f"Stimulated ÷ unstimulated × 100 − 100, with as unstimulated recording {found}."
        if self.partner == NO_PARTNER:
            return "The mean brightness of the ROI in each frame, as recorded."
        return (
            f"The mean brightness of the ROI in each frame, corrected for bleaching with {found}: "
            "stimulated × (mean of the unstimulated over the first baseline window) ÷ unstimulated."
        )

    def response_explanation(self, pulse):
        if self.trace == BRIGHTNESS:
            corrected = " of the bleaching-corrected trace" if self.partner != NO_PARTNER else ""
            return (
                f"{pulse.name} peak ÷ {pulse.baseline} × 100 − 100: the change of brightness{corrected} from the baseline, "
                "in percent (dF/F)."
            )
        return (
            f"{pulse.name} peak − {pulse.baseline}: the rise above the baseline, in percentage points of the "
            "stimulated ÷ unstimulated trace."
        )

    def _slice_measures(self, per_recording, every):
        summary = []
        condition = f"{self.condition_name} ({self.condition_unit})" if self.condition_unit else self.condition_name
        for measure in per_recording:
            for statistic in self.summary_statistics:
                summary.append(
                    Column(f"{measure.name} {statistic}", measure.unit, f"The {statistic} of {measure.name} over the recordings of a slice.", "slice")
                )
            for mean in self.summary_means:
                summary.append(Column(f"{measure.name} mean {mean.name}", measure.unit,
                                      f"The mean of {measure.name} over the recordings of a slice {mean.which(condition)}.",
                                      "slice"))
        if self.summary_baseline_spread:
            for name in self.baselines:
                summary.append(
                    Column(
                        f"{name} spread",
                        "%",
                        f"(largest {name} − smallest {name}) ÷ smallest {name} × 100 over the recordings of a slice: "
                        "how much the baseline drifted.",
                        "slice",
                    )
                )
        units = {measure.name: measure.unit for measure in every}
        for fit in self.condition_fits:
            summary += self._condition_fit_measures(fit, condition, units.get(fit.measure, ""))
        return summary

    def _condition_fit_measures(self, fit, condition, unit):
        x_unit = self.condition_unit or "units of the condition"
        across = f"fitted by least squares to {fit.measure} against the {condition} of the recordings of a slice"
        if fit.model == SATURATION:
            curve = f"top·xⁿ ÷ (halfⁿ + xⁿ), x the {condition}, {across}"
            described = [(x_unit, f"half of {curve}: the {condition} at which the curve reaches half of its top."),
                         (unit, f"top of {curve}: the {fit.measure} the curve approaches at a large {condition}."),
                         ("Hill coefficient", f"n of {curve}.")]
        else:
            fixed = "" if fit.plateau is None else f", with the plateau fixed at {fit.plateau:g}"
            curve = f"plateau − (plateau − start)·exp(−x/τ), x the {condition}, {across}{fixed}"
            described = [(x_unit, f"τ of {curve}: the {condition} by which {fit.measure} has recovered 63 % of the way to "
                                  "the plateau."),
                         (unit, f"start of {curve}: the value of the curve at a {condition} of 0."),
                         (unit, f"plateau of {curve}: the value the curve approaches at a long {condition}.")]
        return [Column(name, unit, text, "slice") for name, (unit, text) in zip(fit.measure_names(), described)]

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def problems(self):
        """What is wrong with the protocol, as sentences. Empty when it can be used."""
        found = []
        if not self.name.strip():
            found.append("The protocol needs a name.")
        if not self.sampling_interval_ms > 0:
            found.append("The time between frames must be more than 0 ms.")
        if not self.pulses:
            found.append("The protocol needs at least one pulse.")
        if self.trace == RATIO and self.partner == NO_PARTNER:
            found.append("A stimulated ÷ unstimulated trace needs an unstimulated partner for each recording.")
        if self.partner == AS_LISTED and self.selection != LISTED:
            found.append("Partners named in the list need a list of recordings, each with its unstimulated partner.")
        if self.trace == BRIGHTNESS and self.partner != NO_PARTNER and not self.baselines:
            found.append("The correction by the unstimulated partner needs a baseline window.")

        names = self.names()
        for name in sorted({n for n in names if names.count(n) > 1}):
            found.append(f"The name {name} is used twice. Every window, pulse, comparison and fit needs its own name.")
        if any(not name.strip() for name in names):
            found.append("Every window, pulse, comparison and fit needs a name.")

        for name, window in self.baselines.items():
            if window == PER_RECORDING:
                if self.selection != LISTED:
                    found.append(f"{name} is set per recording, which needs a list of recordings.")
            else:
                found += _window_problems(name, window)
        for pulse in self.pulses:
            if pulse.baseline not in self.baselines:
                found.append(f"{pulse.name} is measured from the baseline {pulse.baseline}, which does not exist.")
            if pulse.per_recording:
                if self.selection != LISTED:
                    found.append(f"{pulse.name} is set per recording, which needs a list of recordings.")
            else:
                found += _window_problems(f"The peak window of {pulse.name}", pulse.peak)

        if self.selection == LISTED:
            found += self._recording_problems()
        for comparison in self.comparisons:
            for pulse in (comparison.pulse, comparison.relative_to):
                if self.pulse(pulse) is None:
                    found.append(f"The comparison {comparison.name} uses {pulse}, which is not a pulse.")
        for fit in self.fits:
            if fit.after is not None and self.pulse(fit.after) is None:
                found.append(f"The fit {fit.name} starts after {fit.after}, which is not a pulse.")
            least = 6 if fit.kind == DOUBLE else 3
            if fit.start < 0 or fit.length < least:
                found.append(f"The fit {fit.name} needs a start of 0 or more and a length of at least {least} frames.")
        if self.kinetic_measures and self.kinetic_smoothing_frames < 1:
            found.append("The smoothing of the kinetic measures must be at least 1 frame (1 means none).")
        for name in (self.kinetic_pulses or []) + self.spatial_pulses:
            if self.pulse(name) is None:
                found.append(f"Kinetic or spatial measures are chosen for {name}, which is not a pulse.")
        if self.spatial_measures and not self.spatial_pulses:
            found.append("Choose at least one pulse for the spatial measures.")
        for name in self.near_to_far:
            if name not in [c.name for c in self.comparisons]:
                found.append(f"The near-to-far index of {name} needs the comparison {name}.")
        if self.spatial_measures or self.near_to_far:
            found += self.spatial.problems()
        names = [mean.name for mean in self.summary_means]
        if not all(names) or len(set(names)) < len(names):
            found.append("Every mean over recordings of the slice summary needs a name of its own.")
        for mean in self.summary_means:
            if mean.by == BY_FILES and not mean.files:
                found.append(f"The mean over recordings {mean.name} needs at least one file name, such as hi*.")
            if mean.by == BY_CONDITION and mean.low > mean.high:
                found.append(f"The condition range of the mean over recordings {mean.name} must go from low to high.")
        per_recording = {m.name for m in self.recording_measures()}
        for fit in self.condition_fits:
            if fit.measure not in per_recording:
                found.append(f"The fit across conditions {fit.name} uses {fit.measure}, which is not measured per recording.")
        for n, exclusion in enumerate(self.exclusions, 1):
            if exclusion.measure not in per_recording:
                found.append(f"Exclusion {n} uses {exclusion.measure}, which is not measured per recording.")
            if exclusion.by == BY_FILES and not exclusion.files:
                found.append(f"Exclusion {n} needs at least one file name, such as hi*.")
            if exclusion.by == BY_CONDITION and exclusion.low > exclusion.high:
                found.append(f"The condition range of exclusion {n} must go from low to high.")
            if exclusion.relative and not exclusion.factor >= 0:
                found.append(f"The factor k of exclusion {n} must be 0 or more.")
        return found

    def _recording_problems(self):
        found = []
        if not self.recordings:
            found.append("Add at least one recording to the list.")
        files = [recording.file for recording in self.recordings]
        for file in sorted({f for f in files if files.count(f) > 1}):
            found.append(f"{file} is listed twice.")
        for recording in self.recordings:
            label = recording.file or "A listed recording"
            if not recording.file.strip():
                found.append("Every listed recording needs a file name.")
            if self.partner == AS_LISTED and not recording.unstimulated.strip():
                found.append(f"{label} needs an unstimulated partner.")
            for name in self.per_recording_baselines():
                found += _window_problems(f"{name} of {label}", recording.baselines.get(name))
            for name in self.per_recording_pulses():
                timing = recording.pulses.get(name)
                found += _window_problems(f"The peak window of {name} in {label}", timing.peak if timing else None)
        return found

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def to_dict(self):
        return {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "name": self.name,
            "description": self.description,
            "sampling_interval_ms": self.sampling_interval_ms,
            "trace": self.trace,
            "recordings": {
                "measure": self.selection,
                "unstimulated_partner": self.partner,
                "condition": {"name": self.condition_name, "unit": self.condition_unit},
                "skip_words": self.skip_words,
                "windows_follow_condition": self.windows_follow_condition,
                "list": [_recording_to_dict(recording) for recording in self.recordings],
            },
            "baselines": {name: _window_to_json(window) for name, window in self.baselines.items()},
            "pulses": [
                {
                    "name": pulse.name,
                    "stimulus": PER_RECORDING if pulse.per_recording else pulse.stimulus,
                    "peak": PER_RECORDING if pulse.per_recording else _window_to_json(pulse.peak),
                    "baseline": pulse.baseline,
                }
                for pulse in self.pulses
            ],
            "comparisons": [
                {"name": c.name, "pulse": c.pulse, "relative_to": c.relative_to, "as": c.scale} for c in self.comparisons
            ],
            "fits": [{"name": f.name, "kind": f.kind, "after": f.after, "start": f.start, "length": f.length} for f in self.fits],
            "write_peaks": self.write_peaks,
            "kinetics": {
                "measures": self.kinetic_measures,
                "pulses": self.kinetic_pulses,
                "smoothing_frames": self.kinetic_smoothing_frames,
            },
            "spatial": {
                "measures": self.spatial_measures,
                "pulses": self.spatial_pulses,
                "near_to_far": self.near_to_far,
                "settings": self.spatial.to_dict(),
            },
            "slice_summary": {
                "file": self.slice_file,
                "statistics": self.summary_statistics,
                "means": [_mean_to_dict(mean) for mean in self.summary_means],
                "baseline_spread": self.summary_baseline_spread,
                "condition_fits": [
                    {"name": f.name, "measure": f.measure, "model": f.model, "plateau": f.plateau} for f in self.condition_fits
                ],
            },
            "exclusions": [_exclusion_to_dict(exclusion) for exclusion in self.exclusions],
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise ProtocolError("This file is not an EMA evoked protocol.")
        if data.get("format_version", 0) > FORMAT_VERSION:
            raise ProtocolError("This protocol was written by a newer version of EMA.")
        try:
            recordings, summary = data["recordings"], data.get("slice_summary", {})
            kinetic, spatial = data.get("kinetics", {}), data.get("spatial", {})
            protocol = cls(
                name=str(data["name"]),
                description=str(data.get("description", "")),
                sampling_interval_ms=float(data["sampling_interval_ms"]),
                trace=_choice(data["trace"], TRACES, "trace"),
                partner=_choice(recordings.get("unstimulated_partner", _old_partner(data)), PARTNERS, "unstimulated partner"),
                selection=_choice(recordings["measure"], SELECTIONS, "recordings to measure"),
                condition_name=str(recordings.get("condition", {}).get("name", "")),
                condition_unit=str(recordings.get("condition", {}).get("unit", "")),
                skip_words=[str(word) for word in recordings.get("skip_words", [])],
                recordings=[_recording_from_dict(r) for r in recordings.get("list", [])],
                baselines={str(name): _window_from_json(window) for name, window in data["baselines"].items()},
                pulses=[_pulse_from_dict(p) for p in data["pulses"]],
                comparisons=[
                    Comparison(str(c["name"]), str(c["pulse"]), str(c["relative_to"]), _choice(c.get("as", RATIO_SCALE), SCALES, "comparison"))
                    for c in data.get("comparisons", [])
                ],
                fits=[
                    Fit(str(f["name"]), None if f.get("after") is None else str(f["after"]), int(f["start"]), int(f["length"]),
                        _choice(f.get("kind", SINGLE), FIT_KINDS, "kind of fit"))
                    for f in data.get("fits", [])
                ],
                windows_follow_condition=bool(recordings.get("windows_follow_condition", False)),
                kinetic_measures=[_choice(m, KINETIC_KEYS, "kinetic measure") for m in kinetic.get("measures", [])],
                kinetic_pulses=None if kinetic.get("pulses") is None else [str(n) for n in kinetic["pulses"]],
                kinetic_smoothing_frames=int(kinetic.get("smoothing_frames", 3)),
                spatial_measures=[_choice(m, SPATIAL_KEYS, "spatial measure") for m in spatial.get("measures", [])],
                spatial_pulses=[str(n) for n in spatial.get("pulses", ["P1"])],
                near_to_far=[str(n) for n in spatial.get("near_to_far", [])],
                spatial=SpatialSettings.from_dict(spatial.get("settings", {})),
                slice_file=bool(summary.get("file", True)),
                summary_statistics=[_choice(s, STATISTICS, "statistic") for s in summary.get("statistics", [])],
                summary_means=_means_from_dict(summary),
                summary_baseline_spread=bool(summary.get("baseline_spread", False)),
                condition_fits=[
                    ConditionFit(str(f["name"]), str(f["measure"]), _choice(f.get("model", RECOVERY), CONDITION_MODELS, "model"),
                                 None if f.get("plateau") is None else float(f["plateau"]))
                    for f in summary.get("condition_fits", [])
                ],
                write_peaks=bool(data.get("write_peaks", True)),  # protocols saved before it could be chosen wrote them
                exclusions=[_exclusion_from_dict(e) for e in data.get("exclusions", [])],
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            if isinstance(error, ProtocolError):
                raise
            raise ProtocolError(f"The protocol file is incomplete or damaged ({error!r}).") from error
        pulses = {pulse.name for pulse in protocol.pulses}
        for fit in protocol.condition_fits:
            if fit.measure in pulses:  # saved when a pulse's peak column had the pulse's own name
                fit.measure += " peak"
        return protocol

    def save(self, path):
        text = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        # Short lists, such as a window [81, 93], on one line, so the file is easy to read
        text = re.sub(r"\[\s+([^\[\]{}]*?)\s+\]", lambda m: "[" + ", ".join(v.strip() for v in m.group(1).split(",")) + "]", text)
        Path(path).write_text(text + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path):
        """Read a protocol file. Raises OSError, or ProtocolError when it is not a protocol or is damaged."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except ValueError as error:  # not JSON, or not UTF-8 text
            raise ProtocolError(f"{Path(path).name} is not a valid JSON file ({error}).") from error
        return cls.from_dict(data)

# ---------------------------------------------------------------------------
# Reading and writing the parts
# ---------------------------------------------------------------------------


def _old_partner(data):
    """The partner of a protocol written before partners could be chosen: listed for a ratio, none for brightness."""
    return AS_LISTED if data.get("trace") == RATIO else NO_PARTNER


def _window_problems(label, window):
    if window is None:
        return [f"{label} is not set."]
    if not 0 <= window.start < window.end:
        return [f"{label} must start at frame 0 or later and end after it starts."]
    return []


def _choice(value, choices, what):
    if value not in choices:
        raise ProtocolError(f"'{value}' is not a known {what}.")
    return value


def _range(value):
    if value is None:
        return None
    low, high = value
    return [float(low), float(high)]


def _mean_to_dict(mean):
    if mean.by == BY_FILES:
        return {"name": mean.name, "files": mean.files}
    return {"name": mean.name, "condition_range": [mean.low, mean.high]}


def _means_from_dict(summary):
    """The means over recordings of a slice summary. A summary with a condition range instead has that one mean."""
    if "means" not in summary:
        found = _range(summary.get("condition_range"))
        return [] if found is None else [SliceMean(f"{found[0]:g}-{found[1]:g}", BY_CONDITION, *found)]
    means = []
    for saved in summary["means"]:
        if "files" in saved:
            means.append(SliceMean(str(saved["name"]), BY_FILES, files=file_patterns(saved["files"])))
        else:
            low, high = _range(saved["condition_range"])
            means.append(SliceMean(str(saved["name"]), BY_CONDITION, low, high))
    return means


def _exclusion_to_dict(exclusion):
    recordings = ALL_RECORDINGS
    if exclusion.by == BY_FILES:
        recordings = {"files": exclusion.files}
    elif exclusion.by == BY_CONDITION:
        recordings = {"condition_range": [exclusion.low, exclusion.high]}
    return {
        "measure": exclusion.measure,
        "statistic": exclusion.statistic,
        "recordings": recordings,
        "test": exclusion.test,
        "factor": exclusion.factor,
        "limit": exclusion.limit,
        "side": exclusion.side,
        "among": exclusion.among,
    }


def _exclusion_from_dict(data):
    recordings = data.get("recordings", ALL_RECORDINGS)
    exclusion = Exclusion(
        measure=str(data["measure"]),
        statistic=_choice(data.get("statistic", SPREAD_OF_LARGEST), tuple(SLICE_VALUES), "value of a slice"),
        test=_choice(data.get("test", INTERQUARTILE), EXCLUSION_TESTS, "test of an exclusion"),
        factor=float(data.get("factor", 1.5)),
        limit=float(data.get("limit", 0.0)),
        side=_choice(data.get("side", EITHER_SIDE), SIDES, "side of an exclusion"),
        among=_choice(data.get("among", AMONG_ALL), AMONGS, "set of slices"),
    )
    if isinstance(recordings, dict) and "files" in recordings:
        exclusion.by, exclusion.files = BY_FILES, file_patterns(recordings["files"])
    elif isinstance(recordings, dict) and "condition_range" in recordings:
        exclusion.by = BY_CONDITION
        exclusion.low, exclusion.high = _range(recordings["condition_range"])
    elif recordings != ALL_RECORDINGS:
        raise ProtocolError(f"'{recordings}' is not a known choice of recordings for an exclusion.")
    return exclusion


def _window_to_json(window):
    if window == PER_RECORDING:
        return PER_RECORDING
    return None if window is None else window.to_list()


def _window_from_json(value):
    if value == PER_RECORDING:
        return PER_RECORDING
    if value is None:
        return None
    start, end = value
    return Window(int(start), int(end))


def _pulse_from_dict(data):
    per_recording = data.get("peak") == PER_RECORDING
    stimulus = data.get("stimulus")
    return Pulse(
        name=str(data["name"]),
        baseline=str(data["baseline"]),
        peak=None if per_recording else _window_from_json(data.get("peak")),
        stimulus=None if per_recording or stimulus is None else int(stimulus),
        per_recording=per_recording,
    )


def _recording_to_dict(recording):
    return {
        "file": recording.file,
        "unstimulated": recording.unstimulated,
        "condition": recording.condition,
        "baselines": {name: window.to_list() for name, window in recording.baselines.items()},
        "pulses": {
            name: {"stimulus": timing.stimulus, "peak": _window_to_json(timing.peak)}
            for name, timing in recording.pulses.items()
        },
    }


def _recording_from_dict(data):
    condition = data.get("condition")
    return Recording(
        file=str(data["file"]),
        unstimulated=str(data.get("unstimulated", "")),
        condition=None if condition is None else float(condition),
        baselines={str(name): _window_from_json(window) for name, window in data.get("baselines", {}).items()},
        pulses={
            str(name): PulseTiming(
                None if timing.get("stimulus") is None else int(timing["stimulus"]), _window_from_json(timing.get("peak"))
            )
            for name, timing in data.get("pulses", {}).items()
        },
    )
