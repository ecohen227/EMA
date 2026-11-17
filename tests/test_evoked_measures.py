"""Measuring with the built-in protocols gives the numbers of the earlier EMA programs, exactly.

The reference is `ema/analysis.py` of EMA 2.4, whose outputs were checked byte
for byte against EMMA 2P v1.0 and 11P v1.1. It is read from the handoff folder
next to this program (or from the folder in the environment variable
EMA_V2_DIR); without it those tests are skipped.
"""

import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

from ema.evoked import measure, summarise
from ema.evoked.kinetics import kinetics
from ema.evoked.measures import fit_across_conditions, hill, recovery
from ema.evoked.catalogue import KINETIC_KEYS, SPATIAL_KEYS
from ema.evoked.spatial import measure_spatial
from ema.evoked.presets import TRAIN_PEAKS, paired_pulse, paired_pulse_uncorrected, pulse_train
from ema.evoked.protocol import BRIGHTNESS, DOUBLE, SATURATION, Comparison, ConditionFit, Fit, Protocol, Pulse, Window

HANDOFF_V2 = Path(__file__).resolve().parents[2] / "EMA_V3_handoff_2026-11-14" / "EMA_V3_handoff_2026-11-14" / "1_programs" / "EMA_V2"
V2_FOLDER = Path(os.environ.get("EMA_V2_DIR", HANDOFF_V2))
FRAMES = 1649


def transient(start, height, tau=40.0, rise=4.0):
    """A response that rises at frame `start` and decays exponentially."""
    t = np.arange(FRAMES) - start
    return np.where(t >= 0, height * (1 - np.exp(-t / rise)) * np.exp(-t / tau), 0.0)


def brightness_trace(seed, scale=1.0):
    rng = np.random.default_rng(seed)
    bleaching = 600 * (1 - 0.00002 * np.arange(FRAMES))
    return bleaching * (1 + scale * (transient(103, 0.6) + transient(928, 0.3))) + rng.normal(0, 3, FRAMES)


def train_traces(seed, recovery_frame):
    rng = np.random.default_rng(seed)
    base = 700 * (1 - 0.00003 * np.arange(FRAMES))
    train = sum(transient(103 + round(k * 100 / 4.849), 0.3 * 0.85**k, tau=25) for k in range(10))
    stimulated = base * (1 + train + transient(recovery_frame, 0.12, tau=25)) + rng.normal(0, 2, FRAMES)
    unstimulated = base + rng.normal(0, 2, FRAMES)
    return stimulated, unstimulated


@pytest.fixture(scope="module")
def v2():
    path = V2_FOLDER / "ema" / "analysis.py"
    if not path.is_file():
        pytest.skip(f"EMA 2.4 not found at {V2_FOLDER}")
    spec = importlib.util.spec_from_file_location("ema_v2_analysis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# The built-in protocols against EMA 2.4
# ---------------------------------------------------------------------------


def test_paired_pulse_reproduces_the_2p_numbers(v2):
    # The uncorrected protocol is the one that measures the brightness as EMMA 2P did. The corrected one measures the
    # same way on the corrected trace (see test_evoked_protocol.py for the correction).
    protocol = paired_pulse_uncorrected()
    rows, reference = [], {key: [] for key in ("B1", "P1", "B2", "P2", "P1 dF/F (%)", "P2 dF/F (%)", "PPR", "Tau")}
    currents = [50, 100, 200, 300, 400, 500]
    for seed, current in enumerate(currents):
        trace = brightness_trace(seed, scale=current / 300)
        values = measure(protocol, trace).values
        rows.append((float(current), values))

        b1, p1 = trace[81:93].mean(), trace[83:205].max()
        b2, p2 = trace[904:925].mean(), trace[904:1125].max()
        dff1, dff2 = p1 / b1 * 100 - 100, p2 / b2 * 100 - 100  # EMMA 2P v1.0, compute_dff_metrics
        ppr = dff2 / dff1 if dff1 != 0 else np.nan
        tau = v2.tau_ms(v2.fit_exponential(trace, (83, 205), 4, 412), 4.849)
        for key, value in zip(reference, (b1, p1, b2, p2, dff1, dff2, ppr, tau)):
            reference[key].append(value)

        assert (values["B1"], values["P1"], values["B2"], values["P2"]) == (b1, p1, b2, p2)
        assert values["P1 response"] == dff1 and values["P2 response"] == dff2
        assert values["PPR"] == ppr and values["Tau"] == tau

    summary = summarise(protocol, rows)
    expected = v2.slice_summary(reference, currents)
    names = {"P1 dF/F (%)": "P1 response", "P2 dF/F (%)": "P2 response"}
    for key, (low, high, mean, in_range) in expected.items():
        name = names.get(key, key)
        assert summary[f"{name} min"] == low and summary[f"{name} max"] == high and summary[f"{name} mean"] == mean
        assert summary[f"{name} mean 100-400"] == in_range
    assert summary["B1 spread"] == v2.max_abs_diff(reference["B1"])
    assert summary["B2 spread"] == v2.max_abs_diff(reference["B2"])


def test_pulse_train_reproduces_the_11p_numbers(v2):
    protocol = pulse_train()
    for seed, recording in enumerate(protocol.recordings):
        stimulated, unstimulated = train_traces(seed, recording.pulses["P11"].stimulus)
        trace = v2.ratio_trace(stimulated, unstimulated)
        values = measure(protocol, trace, recording).values

        windows = [("BL", (83, 101), True)] + [(f"P{i}", peak, False) for i, peak in enumerate(TRAIN_PEAKS, 1)]
        windows += [("BLPre11", tuple(recording.baselines["BLPre11"].to_list()), True)]
        windows += [("P11", tuple(recording.pulses["P11"].peak.to_list()), False)]
        metrics = v2.train_metrics(trace, windows)
        ratios = v2.train_ratios(metrics, 10)
        normalised = v2.normalized_train(ratios, 10)

        for name in metrics:
            assert values[name] == metrics[name]
        for i in range(1, 11):
            assert values[f"P{i} response"] == ratios[f"P{i}/BL"]
            assert values[f"nP{i}/BL"] == normalised[f"nP{i}/BL"]
        assert values["P11 response"] == ratios["P11/BLPre11"]
        for name in ("P2/P1", "P10/P1", "P11/P1", "P11/P10"):
            assert values[name] == ratios[name]


# ---------------------------------------------------------------------------
# Measures that do not depend on EMA 2.4
# ---------------------------------------------------------------------------


def test_measures_list_matches_the_measured_values():
    for protocol, recording in ((paired_pulse(), None), (pulse_train(), pulse_train().recordings[0])):
        trace = brightness_trace(1) if recording is None else (train_traces(1, 412)[0] / train_traces(1, 412)[1] - 1) * 100
        values = measure(protocol, trace, recording).values
        per_recording = [m.name for m in protocol.measures() if m.per == "recording"]
        assert per_recording == list(values)


def test_a_window_after_the_end_is_reported_not_crashed():
    protocol = paired_pulse()
    protocol.pulses[1].peak = Window(2000, 2100)
    result = measure(protocol, brightness_trace(0))
    assert np.isnan(result.values["P2"]) and np.isnan(result.values["PPR"])
    assert any("P2" in problem and "after the end" in problem for problem in result.problems)


def test_fit_finds_the_time_constant():
    protocol = paired_pulse()
    trace = 600 + 300 * transient(103, 1.0, tau=40.0, rise=0.5)
    tau_ms = measure(protocol, trace).values["Tau"]
    assert tau_ms == pytest.approx(40.0 * 4.849, rel=0.01)


def triangle_protocol(measures, window=Window(100, 200)):
    return Protocol("shape", trace=BRIGHTNESS, sampling_interval_ms=5.0, baselines={"B": Window(0, 50)},
                    pulses=[Pulse("P", "B", window, stimulus=100)], kinetic_measures=measures, kinetic_smoothing_frames=1)


def test_kinetics_of_a_known_transient():
    """A triangle: rises linearly over 10 frames from the stimulus to 50 %, falls linearly over 20."""
    protocol = triangle_protocol(KINETIC_KEYS)
    t = np.arange(400, dtype=float)
    rise, fall = np.clip((t - 100) / 10, 0, 1), np.clip(1 - (t - 110) / 20, 0, 1)
    noise = np.where(t < 50, np.resize([-0.5, 0.5], 400), 0.0)  # baseline alternating 99.5 and 100.5: SD 0.5 %
    trace = 100 * (1 + 0.5 * np.where(t <= 110, rise, fall)) + noise
    found = kinetics(protocol, trace, 100.0, Window(0, 50), 100, Window(100, 200))

    # the parabola through frames 109, 110 and 111 (45 %, 50 %, 47.5 %) peaks 1/6 frame after frame 110
    assert found["time to peak"] == pytest.approx((10 + 1 / 6) * 5.0)
    assert found["onset"] == pytest.approx(2 * 5.0)  # 20 % of the way up
    assert found["rise 10-90"] == pytest.approx(8 * 5.0)
    assert found["rise 20-80"] == pytest.approx(6 * 5.0)
    assert found["max rise slope"] == pytest.approx(5.0 / 0.005)  # 5 % per 5 ms frame
    assert found["max decay slope"] == pytest.approx(2.5 / 0.005)  # falls 2.5 % per frame
    assert found["half-width"] == pytest.approx((5 + 10) * 5.0)  # 5 frames rising above half, 10 falling
    assert found["half-decay"] == pytest.approx(10 * 5.0)
    assert found["1/e decay"] == pytest.approx(20 * (1 - np.exp(-1)) * 5.0)
    assert found["area"] == pytest.approx(50 * 15 * 5.0 / 1000, rel=0.05)  # triangle: half of 50 % times 30 frames
    assert found["signal-to-noise"] == pytest.approx(50 / 0.5, rel=0.02)


def test_kinetics_are_nan_when_the_response_has_not_decayed_inside_the_window():
    protocol = triangle_protocol(["half-decay", "time to peak"], window=Window(100, 115))
    trace = 100 + 50 * transient(100, 1.0, tau=40, rise=1)
    found = kinetics(protocol, trace, 100.0, Window(0, 50), 100, Window(100, 115))
    assert np.isnan(found["half-decay"]) and found["time to peak"] > 0


def test_kinetics_only_on_the_chosen_pulses():
    protocol = paired_pulse()
    protocol.kinetic_measures, protocol.kinetic_pulses = ["time to peak"], ["P2"]
    values = measure(protocol, brightness_trace(0)).values
    assert "P2 time to peak" in values and "P1 time to peak" not in values


def test_double_exponential_fit_finds_both_time_constants():
    protocol = paired_pulse()
    protocol.fits = [Fit("Decay", "P1", 2, 600, DOUBLE)]
    t = np.arange(FRAMES) - 110.0
    trace = 600 + np.where(t >= 0, 200 * np.exp(-np.clip(t, 0, None) / 8.0) + 100 * np.exp(-np.clip(t, 0, None) / 80.0), 0)
    trace[100:110] = np.linspace(600, 900, 10)
    values = measure(protocol, trace).values
    assert values["Decay fast"] == pytest.approx(8 * 4.849, rel=0.02)
    assert values["Decay slow"] == pytest.approx(80 * 4.849, rel=0.02)
    fast, slow = 200 * np.exp(-1 / 8), 100 * np.exp(-1 / 80)  # at the fit's first frame: 2 frames after the maximum at 109
    assert values["Decay fast fraction"] == pytest.approx(fast / (fast + slow), abs=0.01)


# ---------------------------------------------------------------------------
# Spatial measures, on synthetic movies with known answers
# ---------------------------------------------------------------------------


def spatial_protocol(**changes):
    protocol = Protocol("maps", sampling_interval_ms=5.0, baselines={"B1": Window(5, 25), "B2": Window(85, 105)},
                        pulses=[Pulse("P1", "B1", Window(30, 60), stimulus=30), Pulse("P2", "B2", Window(110, 140), stimulus=110)],
                        comparisons=[Comparison("PPR", "P2", "P1")], spatial_measures=list(SPATIAL_KEYS), spatial_pulses=["P1"])
    protocol.spatial.smoothing_px = 0
    for name, value in changes.items():
        setattr(protocol, name, value)
    return protocol


def movie_with(maps, frames=200, shape=(128, 128)):
    """A movie at 1000 counts that steps up by `map` (in %) from each start frame on, for 20 frames."""
    movie = np.full((frames, *shape), 1000.0)
    for start, image in maps:
        movie[start : start + 20] *= 1 + image / 100
    return movie


def test_footprint_of_a_lorentzian_map():
    y, x = np.indices((128, 128))
    r_um = np.hypot(x - 64, y - 64) * 16
    image = 50 / (1 + (r_um / 300) ** 2)
    protocol = spatial_protocol()
    movie = movie_with([(30, image)])
    trace = movie[:, 54:75, 54:75].mean(axis=(1, 2))
    result = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, trace))
    assert result.values["P1 footprint width"] == pytest.approx(300, rel=0.02)
    assert result.values["P1 footprint half-width"] == pytest.approx(300, rel=0.06)  # a Lorentzian is at half its height at r = width
    assert result.values["P1 centroid offset"] < 5
    assert 0 < result.values["P1 tail fraction"] < 1 and result.values["P1 r50"] > 100


def test_centroid_offset_of_a_shifted_spot():
    y, x = np.indices((128, 128))
    image = 40 * np.exp(-((x - 74) ** 2 + (y - 64) ** 2) / (2 * 8.0**2))  # 10 px right of the ROI centre
    protocol = spatial_protocol(spatial_measures=["centroid offset"])
    movie = movie_with([(30, image)])
    result = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, movie[:, 60:68, 70:78].mean(axis=(1, 2))))
    assert result.values["P1 centroid offset"] == pytest.approx(160, rel=0.1)


def test_electrode_pixels_are_left_out_of_the_rings():
    y, x = np.indices((128, 128))
    image = np.full((128, 128), 30.0)
    electrode = (np.abs(y - 64) < 3) & (x < 64)
    image[electrode] = 0  # the electrode hides the response
    protocol = spatial_protocol(spatial_measures=["centroid offset"])
    movie = movie_with([(30, image)])
    trace = movie[:, 60:68, 60:68].mean(axis=(1, 2))
    with_mask = measure_spatial(protocol, movie, (64, 64), electrode, measure(protocol, trace))
    assert with_mask.values["P1 centroid offset"] < 1  # the hidden pixels count as their ring's average
    profile = with_mask.profiles["P1"]
    assert np.nanstd(profile[:30]) < 1e-6  # every ring has the same mean: the zeros under the electrode are left out
    protocol.spatial.exclude_electrode = False
    without = measure_spatial(protocol, movie, (64, 64), electrode, measure(protocol, trace))
    assert without.values["P1 centroid offset"] > 5


def test_near_to_far_index():
    y, x = np.indices((128, 128))
    r_um = np.hypot(x - 64, y - 64) * 16
    first = np.full((128, 128), 40.0)
    second = np.where(r_um < 200, 20.0, 10.0)  # P2/P1 = 0.5 near the centre, 0.25 far from it
    protocol = spatial_protocol(spatial_measures=[], near_to_far=["PPR"])
    movie = movie_with([(30, first), (110, second)])
    trace = movie[:, 60:68, 60:68].mean(axis=(1, 2))
    result = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, trace))
    assert result.values["PPR near-to-far"] == pytest.approx(0.5, rel=0.01)


def test_release_spread_of_a_wave_moving_outwards():
    """Release starts later further out: 1 frame (5 ms) per 4 pixels (64 µm), i.e. 78 ms per mm."""
    y, x = np.indices((128, 128))
    distance = np.hypot(x - 64, y - 64)
    t = np.arange(200)[:, None, None]
    onset = 30 + distance / 4
    rise = np.clip((t - onset) / 4, 0, 1) * np.exp(-np.clip(t - onset - 4, 0, None) / 30)
    rng = np.random.default_rng(0)
    movie = 1000 * (1 + 0.4 * rise) + rng.normal(0, 1, (200, 128, 128))
    protocol = spatial_protocol(spatial_measures=["latency slope", "far-near delay"])
    protocol.pulses[0].peak = Window(30, 90)
    trace = movie[:, 54:75, 54:75].mean(axis=(1, 2))
    result = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, trace))
    assert result.values["P1 latency slope"] == pytest.approx(5.0 / 0.064, rel=0.1)
    # near band 0-160 µm (mean 80 µm), far band 400-640 µm (mean 520 µm): 440 µm apart
    assert result.values["P1 far-near delay"] == pytest.approx(0.44 * 5.0 / 0.064, rel=0.15)


def test_elongation_of_an_oval_spot():
    y, x = np.indices((128, 128))
    image = 40 * np.exp(-((x - 64) ** 2 / (2 * 12.0**2) + (y - 64) ** 2 / (2 * 6.0**2)))  # twice as wide as high
    protocol = spatial_protocol(spatial_measures=["elongation"])
    protocol.spatial.region_um = 960.0  # 5 SDs along the long axis: the region does not cut the spot short
    movie = movie_with([(30, image)])
    result = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, movie[:, 60:68, 60:68].mean(axis=(1, 2))))
    assert result.values["P1 elongation"] == pytest.approx(2.0, rel=0.05)


# ---------------------------------------------------------------------------
# Decay with distance
# ---------------------------------------------------------------------------


def decaying_movie(tau_frames, frames=260, start=30):
    """A Lorentzian footprint (λ = 300 µm) that appears at `start` and fades at every pixel with its own time
    constant `tau_frames(r)`, r in µm from the centre."""
    y, x = np.indices((128, 128))
    r_um = np.hypot(x - 64, y - 64) * 16
    tau = tau_frames(r_um)
    movie = np.full((frames, 128, 128), 1000.0)
    for frame in range(start, frames):
        movie[frame] *= 1 + 0.5 * np.exp(-(frame - start) / tau) / (1 + (r_um / 300) ** 2)
    return movie


def decay_protocol():
    protocol = spatial_protocol(spatial_measures=["far-near decay ratio", "decay-distance slope"])
    protocol.pulses = [Pulse("P1", "B1", Window(30, 60), stimulus=30)]
    protocol.comparisons = []
    protocol.spatial.frames_before_peak = 0  # bins start at the peak, so each ring's bins sample a clean exponential
    return protocol


def test_a_response_that_fades_alike_everywhere():
    protocol = decay_protocol()
    movie = decaying_movie(lambda r: np.full_like(r, 40.0))
    values = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, movie[:, 60:68, 60:68].mean(axis=(1, 2)))).values
    assert values["P1 far-near decay ratio"] == pytest.approx(1.0, abs=0.01)
    assert abs(values["P1 decay-distance slope"]) < 1


def test_a_response_that_fades_faster_far_from_the_centre():
    """τ falls from 40 frames at the centre by 10 frames per 640 µm. Each ring falls to half ln 2 · τ after the first
    bin, whose middle is 1.5 frames after the peak: the slope is −10/640 · ln 2 · 5 ms per µm = −54.2 ms/mm."""
    protocol = decay_protocol()
    movie = decaying_movie(lambda r: 40.0 - 10.0 * r / 640)
    result = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, movie[:, 60:68, 60:68].mean(axis=(1, 2))))
    values = result.values
    assert values["P1 decay-distance slope"] == pytest.approx(-10 / 640 * np.log(2) * 5.0 * 1000, rel=0.05)
    near_tau, far_tau = 40 - 10 * 88 / 640, 40 - 10 * 520 / 640  # at the mean distance of each band's rings
    expected = (1.5 + far_tau * np.log(2)) / (1.5 + near_tau * np.log(2))
    assert values["P1 far-near decay ratio"] == pytest.approx(expected, rel=0.03)
    assert result.decays["P1"].times_ms[0] == pytest.approx(1.5 * 5.0)


def test_the_decay_is_followed_up_to_the_next_stimulus():
    protocol = decay_protocol()
    protocol.pulses.append(Pulse("P2", "B2", Window(110, 140), stimulus=110))
    movie = decaying_movie(lambda r: np.full_like(r, 40.0))
    result = measure_spatial(protocol, movie, (64, 64), None, measure(protocol, movie[:, 60:68, 60:68].mean(axis=(1, 2))))
    assert result.decays["P1"].times_ms[-1] < (110 - 30) * 5.0


# ---------------------------------------------------------------------------
# Fits across conditions
# ---------------------------------------------------------------------------


def test_recovery_fit_across_delays():
    delays = [500.0, 1000.0, 2500.0, 5000.0]
    values = list(recovery(np.array(delays), 10.0, 100.0, 2000.0))
    fixed = fit_across_conditions(ConditionFit("Recovery", "P11/P1", plateau=100.0), delays, values)
    assert fixed["Recovery time constant"] == pytest.approx(2000.0, rel=1e-4) and "Recovery plateau" not in fixed
    free = fit_across_conditions(ConditionFit("Recovery", "P11/P1"), delays, values)
    assert free["Recovery plateau"] == pytest.approx(100.0, rel=1e-3)
    too_few = fit_across_conditions(ConditionFit("Recovery", "P11/P1"), delays[:3], values[:3])
    assert np.isnan(too_few["Recovery time constant"])  # 3 recordings cannot fit 3 parameters with any check


def test_input_output_fit_across_currents():
    currents = [50.0, 100.0, 200.0, 300.0, 400.0, 500.0]
    values = list(hill(np.array(currents), 80.0, 180.0, 2.5))
    found = fit_across_conditions(ConditionFit("IO", "P1 response", SATURATION), currents, values)
    assert found["IO half-max"] == pytest.approx(180.0, rel=1e-3) and found["IO max"] == pytest.approx(80.0, rel=1e-3)
    assert found["IO steepness"] == pytest.approx(2.5, rel=1e-3)
    linear = fit_across_conditions(ConditionFit("IO", "P1 response", SATURATION), currents, [c / 10 for c in currents])
    assert np.isnan(linear["IO half-max"])  # no sign of saturation: the half-max would be far beyond the data


def test_slice_summary_includes_the_fits_across_conditions():
    protocol = paired_pulse_uncorrected()
    protocol.condition_fits = [ConditionFit("IO", "P1 response", SATURATION)]
    rows = [(float(c), {"P1 response": hill(c, 80.0, 180.0, 2.5)}) for c in (50, 100, 200, 300, 400, 500)]
    summary = summarise(protocol, rows)
    assert summary["IO half-max"] == pytest.approx(180.0, rel=1e-3)
    names = [m.name for m in protocol.measures() if m.per == "slice"]
    assert names[-3:] == ["IO half-max", "IO max", "IO steepness"]
