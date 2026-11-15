"""The full description of every measure a protocol can produce, for the documentation.

metrics.py gives each kinetic and spatial measure a one-line definition
(shown in the configurator); this file gives the rest: the formula, exactly
how it is computed, when it is left empty, what it reflects, and what to be
careful of. BASIC and SLICE describe the measures every protocol has
(baselines, peaks, responses, comparisons, fits, slice summaries). The
measure reference page of the documentation is generated from this file, and
a test makes sure every measure is described here.

The words "trace", "response", "smoothed response", "stretch", "response
map", "ring", "band", "bin" and "Theil–Sen slope" are defined once on that
page.
"""

# Each entry: title, name (how the measure is named), unit, definition, formula, method, empty, meaning,
# caveats, example. The kinetic and spatial ones take their name, unit and definition from metrics.py.

BASIC = [
    dict(
        key="baseline",
        title="Baseline",
        name="the baseline window's own name, for example ``B1``, ``BL`` or ``BLPre11``",
        unit="counts with a brightness trace; % with a stimulated ÷ unstimulated trace",
        definition="The mean of the trace over the baseline window.",
        formula="(trace(start) + trace(start + 1) + … + trace(end − 1)) ÷ the number of these frames",
        method="The window runs from its first frame *start* up to, but not including, its frame *end*. A window that "
               "runs past the end of the recording is cut at its last frame. A baseline set per recording uses the "
               "window in the recording's row of the list of recordings.",
        empty="The window is not set, or starts after the last frame of the recording.",
        meaning="The resting level a pulse is measured from. With a brightness trace it is the mean brightness of the "
                "ROI (corrected for bleaching when the recording has an unstimulated partner); with a stimulated ÷ "
                "unstimulated trace, how far the stimulated recording sits above its partner, in %.",
        caveats="A baseline right before a pulse of a train still holds the decay of the pulses before it. In a "
                "corrected brightness trace the baselines are on the scale of the stimulated recording: the first "
                "baseline window is where the correction factor is 1 on average.",
        example="Trace values averaging 600 counts over frames 81 to 92 (window [81, 93]) give B1 = 600 counts.",
    ),
    dict(
        key="peak",
        title="Peak",
        name="the pulse's name, for example ``P1``",
        unit="as the baseline",
        definition="The maximum of the trace over the pulse's peak window.",
        formula="the largest of trace(start), trace(start + 1), …, trace(end − 1)",
        method="Of the trace itself, not smoothed. Its frame (the first one, if the largest value occurs twice) is "
               "the *peak frame* of the pulse: fits that follow the pulse start from it, and its response map is "
               "centred on it. A window past the end of the recording is cut at its last frame. A pulse set per "
               "recording uses the window in the recording's row.",
        empty="The peak window is not set, or starts after the last frame of the recording.",
        meaning="The highest point the trace reaches with the pulse, the baseline still in it.",
        caveats="The maximum of a noisy trace sits above the true top, by roughly the noise SD × √(2 ln n) for n "
                "frames of flat trace: more for long windows and small responses. A window that also covers the "
                "end of an earlier response can take its maximum there.",
        example="Trace values over the window of P1 whose largest is 900 counts, at frame 112: P1 = 900 counts, "
                "peak frame 112.",
    ),
    dict(
        key="response brightness",
        title="Response, with a brightness trace (dF/F)",
        name="``<pulse> response``, for example ``P1 response``",
        unit="%",
        definition="The change from the baseline to the peak, in percent of the baseline.",
        formula="peak ÷ baseline × 100 − 100",
        method="The baseline is the one the pulse is measured from (the *Baseline* column on the *Pulses and "
               "windows* tab).",
        empty="The peak or the baseline is empty.",
        meaning="How much the pulse raised the brightness, relative to the resting brightness: release as seen by "
                "the sensor.",
        caveats="dF/F is independent of how much sensor is expressed only if all the light comes from the sensor; "
                "light from elsewhere (autofluorescence, a camera offset, scattered light) lowers it, most where "
                "the sensor is dim. A saturated sensor compresses large responses. The noise bias of the peak "
                "carries over.",
        example="B1 = 600 counts and P1 = 900 counts: 900 ÷ 600 × 100 − 100 = 50 %.",
    ),
    dict(
        key="response ratio",
        title="Response, with a stimulated ÷ unstimulated trace",
        name="``<pulse> response``, for example ``P1 response``",
        unit="percentage points (of the unstimulated brightness)",
        definition="The rise from the baseline to the peak.",
        formula="peak − baseline",
        method="Both are in % of the unstimulated partner's brightness, so their difference is in percentage "
               "points.",
        empty="The peak or the baseline is empty, or the baseline is exactly 0.",
        meaning="The rise caused by the pulse, as a share of the brightness of the unstimulated recording.",
        caveats="Close to, but not the same as, dF/F: it is relative to the unstimulated brightness, not to the "
                "stimulated recording's own baseline. The two differ by the factor 1 + baseline ÷ 100, within a few "
                "% when the baseline is near 0.",
        example="BL = −1.0 % and P1 = 33.0 %: 33.0 − (−1.0) = 34.0 percentage points.",
    ),
    dict(
        key="comparison",
        title="Comparison",
        name="the comparison's own name, for example ``PPR``, ``P2/P1`` or ``nP3/BL``",
        unit="ratio, or % when it is given as percent",
        definition="The response of one pulse divided by the response of another.",
        formula="response of the pulse ÷ response of the pulse it is relative to (× 100 as percent)",
        method="Of the two responses defined above, measured on the same recording.",
        empty="Either response is empty, or the response it is divided by is 0.",
        meaning="Short-term plasticity: below 1 (100 %) the pulse releases less than the one it is compared with "
                "(depression), above it more (facilitation).",
        caveats="A response near 0 in the denominator makes the ratio unstable (for example the recovery pulse "
                "relative to the last pulse of a train). Responses within a 10 Hz train include the decay of the "
                "pulses before them. Over repeated trials, average the responses before dividing: the mean of "
                "ratios is biased upwards.",
        example="P1 response 50 % and P2 response 30 %: PPR = 30 ÷ 50 = 0.6, or 60 % as percent.",
    ),
    dict(
        key="single fit",
        title="Single exponential fit",
        name="the fit's name, for example ``Tau``",
        unit="ms",
        definition="The time constant τ of A·exp(−t ÷ τ) + C fitted to the trace.",
        formula="A, τ and C that make Σ (trace(t₀ + t) − A·exp(−t ÷ τ) − C)² smallest over the fitted frames, "
                "t = 0, 1, 2, … counted in frames from the first fitted frame t₀; τ in ms = τ in frames × frame "
                "interval",
        method="The fit starts *start* frames after the peak frame of the pulse it follows (or at frame *start* when "
               "it follows no pulse) and covers *length* frames, cut at the end of the recording. A, τ and C are "
               "free. The least-squares search (SciPy's curve_fit, Levenberg–Marquardt) starts from A = largest − "
               "smallest value of the fitted frames, τ = 50 frames, C = their smallest value.",
        empty="The pulse it follows has no usable peak window, fewer than 3 frames are left to fit, or the fit does "
              "not converge.",
        meaning="How fast the response decays: mainly uptake, together with the sensor's own off-rate.",
        caveats="τ is not bounded: a stretch that does not decay can give a very long or a negative τ. Starting on "
                "the rounded top of the response lengthens τ; bleaching left in the trace shortens it. Check it "
                "against the 1/e decay (Kinetics tab).",
        example="Fitted frames falling as 400·exp(−t ÷ 80) + 600 (t in frames): τ = 80 frames × 4.849 ms = 388 ms.",
    ),
    dict(
        key="double fit",
        title="Double exponential fit",
        name="``<fit> fast``, ``<fit> slow`` and ``<fit> fast fraction``, for example ``Tau fast``",
        unit="ms, ms, fraction",
        definition="τ1 and τ2 (τ1 the shorter) and A1 ÷ (A1 + A2) of A1·exp(−t ÷ τ1) + A2·exp(−t ÷ τ2) + C fitted "
                   "to the trace.",
        formula="least squares as for the single fit, with five parameters",
        method="The same frames as a single fit. The search starts from A1 = 0.6 and A2 = 0.4 × (first − last value "
               "of the fitted frames), τ1 = 80 ms, τ2 = 600 ms, C = the last value, with A1 and A2 at least 0 and "
               "τ1 and τ2 between 0.2 and 1 000 000 frames. Whichever component has the shorter τ is called fast. "
               "The fast fraction is the fast component's share of the decay at the first fitted frame.",
        empty="As for the single fit, with at least 6 frames; the fast fraction also when A1 + A2 is 0.",
        meaning="Two decay processes of clearly different speed, for example fast clearance near release sites and "
                "slower clearance of dopamine that spread further.",
        caveats="A double fit always fits at least as well as a single one, so a better fit is no evidence of two "
                "processes; trust it when the two τ differ by about 3 times or more and both amplitudes are clearly "
                "above 0. It cannot tell the sensor's off-rate from clearance. Drift and bleaching inflate the slow "
                "component.",
        example="Fitted frames falling as 200·exp(−t ÷ 8) + 100·exp(−t ÷ 80) + 600 (t in frames): fast = 8 × 4.849 "
                "= 39 ms, slow = 388 ms, fast fraction = 200 ÷ 300 = 0.67.",
    ),
]

SLICE = [
    dict(
        key="statistics",
        title="Minimum, maximum and mean",
        name="``<measure> min``, ``<measure> max``, ``<measure> mean``, for example ``PPR mean``",
        unit="as the measure",
        definition="The smallest, largest and mean value of a per-recording measure over the recordings of a slice.",
        formula="min, max and (sum ÷ number) of the values that are not empty",
        method="A slice is one recording folder. Every per-recording measure of the protocol is summarised, the "
               "kinetic and spatial ones included.",
        empty="Every recording's value is empty.",
        meaning="The range and the average of a measure in one slice.",
        caveats="The recordings of a slice usually differ in their condition (current, delay): the mean over all of "
                "them mixes conditions. For a measure that changes with the condition, prefer the mean over a "
                "range or a fit across conditions.",
        example="PPR of 0.55, 0.60 and empty in three recordings: PPR min = 0.55, max = 0.60, mean = 0.575.",
    ),
    dict(
        key="range mean",
        title="Mean over a range of conditions",
        name="``<measure> mean <low>-<high>``, for example ``P1 response mean 100-400``",
        unit="as the measure",
        definition="The mean of a per-recording measure over the recordings whose condition is from low to high, "
                   "both included.",
        formula="sum ÷ number of the values that are not empty, of the recordings with low ≤ condition ≤ high",
        method="The condition of a recording is the first number in its file name when every stimulated recording is "
               "measured (200 for ``200uA.tif``), and the value typed in its row in a list of recordings. A "
               "recording without a condition is left out.",
        empty="No recording in the range has a value.",
        meaning="An average over the conditions where the measure is comparable, for example the currents that give "
                "clear but not saturated responses.",
        caveats="Which recordings fall in the range depends on the currents recorded in each slice; slices recorded "
                "at different currents average different things.",
        example="Recordings at 50, 100, 200, 300, 400 and 500 µA with the range 100 to 400: the mean of the "
                "recordings at 100, 200, 300 and 400 µA.",
    ),
    dict(
        key="baseline spread",
        title="Baseline spread",
        name="``<baseline> spread``, for example ``B1 spread``",
        unit="%",
        definition="How much a baseline differs between the recordings of a slice.",
        formula="(largest − smallest) ÷ smallest × 100 over the recordings of the slice",
        method="Of the baseline itself (the mean of its window).",
        empty="Any recording's baseline is empty.",
        meaning="How much the resting brightness drifted or differed during the experiment: a quality check.",
        caveats="Bleaching between recordings, focus drift and changes of the light all add to it.",
        example="B1 of 600, 630 and 660 counts: (660 − 600) ÷ 600 × 100 = 10 %.",
    ),
    dict(
        key="recovery fit",
        title="Fit across conditions: recovery",
        name="``<fit> time constant``, ``<fit> start`` and, with a free plateau, ``<fit> plateau``",
        unit="the condition's unit (time constant); the measure's unit (start, plateau)",
        definition="τ, start and plateau of y = plateau − (plateau − start)·exp(−x ÷ τ) fitted to a per-recording "
                   "measure y against the recordings' condition x, over the recordings of a slice.",
        formula="least squares over the recordings whose measure is not empty",
        method="The plateau is either fixed (for example at 100 % for full recovery) or fitted. The search starts "
               "from start = y of the smallest x, plateau = y of the largest x, τ = the median x. The fit needs at "
               "least 3 recordings with different conditions with a fixed plateau, 4 with a free one. τ must lie "
               "between 1/1000 and 10 times the largest condition, and not at either limit.",
        empty="Too few recordings, a fit that does not converge, or a τ outside its limits.",
        meaning="How fast a response recovers, for example the recovery pulse relative to the first pulse against "
                "the delay after the train.",
        caveats="With 4 delays the fit has little freedom; compare groups of slices rather than single slices. A "
                "free plateau cannot be fitted when the longest delay is much shorter than full recovery.",
        example="P11/P1 of 29.9, 45.4, 74.2 and 92.6 % at 500, 1000, 2500 and 5000 ms, with the plateau fixed "
                "at 100 %: time constant 2000 ms, start 10 %.",
    ),
    dict(
        key="saturation fit",
        title="Fit across conditions: saturation (input–output)",
        name="``<fit> half-max``, ``<fit> max`` and ``<fit> steepness``",
        unit="the condition's unit (half-max); the measure's unit (max); none (steepness)",
        definition="half, top and n of y = top·xⁿ ÷ (halfⁿ + xⁿ) fitted to a per-recording measure y against the "
                   "recordings' condition x, over the recordings of a slice.",
        formula="least squares over the recordings whose measure is not empty",
        method="The search starts from top = the largest y, half = the median x, n = 2, with half between 1/1000 "
               "and 10 times the largest condition and n between 0.3 and 20. The fit needs at least 4 recordings "
               "with different conditions, none below 0; a half or n at a limit gives empty values.",
        empty="Too few recordings, a fit that does not converge, or a half or n at its limits (for example when the "
              "responses grow in a straight line, without a sign of saturation).",
        meaning="The current that gives half of the largest response (how easily release is recruited), the "
                "largest response, and how steeply the response grows around the half-max current.",
        caveats="The top of a curve in dF/F can be the sensor's ceiling rather than release's: compare half-max "
                "currents rather than maxima when the sensor may saturate.",
        example="Responses of 3.1, 15.0, 45.2, 62.6, 70.4 and 74.2 % at 50, 100, 200, 300, 400 and 500 µA: "
                "half-max 180 µA, max 80 %, steepness 2.5.",
    ),
]

KINETIC_DETAILS = {
    "time to peak": dict(
        formula="(peak frame + δ − stimulus frame) × frame interval, with δ = ½ (y₋ − y₊) ÷ (y₋ − 2y₀ + y₊)",
        method="The peak frame is the frame of the maximum of the smoothed response inside the pulse's peak window; "
               "y₀ is its value and y₋, y₊ those of the frames before and after it. δ places the top of the parabola "
               "through these three points between frames; it is kept between −0.5 and 0.5, and is 0 when the peak "
               "is the first or last frame of the peak window or when the three points do not bend downwards.",
        empty="The pulse has no stimulus frame, or its response is not above its baseline at the peak.",
        meaning="How long release, diffusion to the sensor and the sensor's own rise take together.",
        caveats="The rise of a fast sensor lasts only a few frames, so the time to peak is close to the frame "
                "interval itself; differences of a fraction of a frame are not reliable. The stimulus is not locked "
                "to the frames, which adds up to half a frame of jitter. The sensor's rise is part of it.",
        example='50.8 ms: the parabola through frames 109, 110 and 111 (45, 50 and 47.5 %) peaks 1/6 frame after frame 110, 10 1/6 frames after the stimulus.'
    ),
    "onset": dict(
        formula="(t20 − stimulus frame) × frame interval, where t20 is the frame at which the smoothed response, "
                "going back from its peak, first falls to 20 % of the peak",
        method="From the peak frame back towards the start of the stretch, the first frame at or below 20 % of the peak "
               "is found; the crossing is placed between it and the frame after it by straight-line interpolation.",
        empty="No stimulus frame, or the response does not fall to 20 % of its peak before the peak within the stretch "
              "(for example a pulse of a train that starts on the decay of the one before).",
        meaning="When the response first becomes clearly visible after the stimulus.",
        caveats="A fixed fraction of the peak, so it does not depend on the size of the response; it does depend on the "
                "noise and on the smoothing. One frame is 4.849 ms: differences much smaller than that are not reliable.",
        example='10 ms: 20 % of the 50 % peak is reached 2 frames after the stimulus.'
    ),
    "rise 10-90": dict(
        formula="(t90 − t10) × frame interval, both crossings found going back from the peak as for the onset",
        method="t10 and t90 are the interpolated frames at which the smoothed response, going back from its peak, "
               "first falls to 10 % and to 90 % of the peak.",
        empty="The response does not fall to 10 % of its peak before the peak within the stretch.",
        meaning="How fast the response rises; with a fast sensor, how synchronous release is.",
        caveats="Fast rises last only a few frames: a rise shorter than about one frame interval cannot be measured. "
                "The 3-frame running mean lengthens short rises. Prefer the 20-80 % rise when the baseline is noisy.",
        example='40 ms: from 5 % (1 frame after the stimulus) to 45 % (9 frames after).'
    ),
    "rise 20-80": dict(
        formula="(t80 − t20) × frame interval",
        method="As for the 10-90 % rise, with 20 % and 80 % of the peak.",
        empty="The response does not fall to 20 % of its peak before the peak within the stretch.",
        meaning="As the 10-90 % rise, less sensitive to noise at the foot and the top of the rise.",
        caveats="As for the 10-90 % rise.",
        example='30 ms: from 10 % (2 frames) to 40 % (8 frames).'
    ),
    "max rise slope": dict(
        formula="max over the rise of (response(k + 1) − response(k)) ÷ frame interval in seconds",
        method="The largest difference between two consecutive frames of the smoothed response from the start of the "
               "stretch to the peak frame, in percent per second.",
        empty="Fewer than two frames between the start of the stretch and the peak.",
        meaning="The fastest increase of the signal: grows with both the amount and the synchrony of release.",
        caveats="Scales with the size of the response; compare it with the response or use the rise times for the "
                "shape alone. Limited by the sensor's rise and by the frame interval.",
        example='1000 %/s: 5 % per 5 ms frame.'
    ),
    "max decay slope": dict(
        formula="−min over the decay of (response(k + 1) − response(k)) ÷ frame interval in seconds",
        method="The largest fall between two consecutive frames of the smoothed response from the peak frame to the end "
               "of the peak window, given as a positive number in percent per second.",
        empty="The peak is at the last frame of the stretch.",
        meaning="The fastest clearance seen by the sensor. In voltammetry the steepest fall tracks the maximal uptake "
                "rate (Vmax) of the transporter.",
        caveats="Grows with the size of the response (with saturable uptake the fall is steepest at high "
                "concentration), so compare responses of similar size. A slow sensor caps it at about "
                "peak ÷ sensor off-time constant. Noisy: it rests on one pair of frames.",
        example='500 %/s: 2.5 % per frame.'
    ),
    "half-width": dict(
        formula="(t50 after the peak − t50 before the peak) × frame interval",
        method="The interpolated frames at which the smoothed response falls to half of its peak, going back from the "
               "peak (rise) and going forward from it (decay), within the stretch.",
        empty="The response does not fall to half of its peak on either side within the stretch: in particular when "
              "the peak window ends before the response has decayed to half.",
        meaning="How long the response lasts: release duration, clearance and the sensor's off-rate together.",
        caveats="Needs a peak window long enough for the decay. In a fast train the next pulse arrives first.",
        example='75 ms: above 25 % from 5 frames after the stimulus to 10 frames after the peak, 15 frames.'
    ),
    "half-decay": dict(
        formula="(t50 after the peak − peak frame) × frame interval",
        method="As the half-width, on the decay only.",
        empty="The response does not fall to half of its peak before the end of the peak window.",
        meaning="How fast the transmitter is cleared, if the sensor is fast enough; it lengthens when uptake is "
                "blocked.",
        caveats="With saturable uptake the half-decay grows with the peak concentration, so compare responses of "
                "similar size. A sensor slower than the clearance (several GRAB-DA variants) measures its own "
                "off-rate instead. Bleaching left in the trace shortens it; use an unstimulated partner.",
        example='50 ms: 10 frames from the peak to 25 %.'
    ),
    "1/e decay": dict(
        formula="(t37 after the peak − peak frame) × frame interval, at 1/e = 36.8 % of the peak",
        method="As the half-decay, at 36.8 % of the peak. For a single exponential decay starting at the peak it "
               "equals the time constant τ.",
        empty="The response does not fall to 36.8 % of its peak before the end of the peak window.",
        meaning="A model-free stand-in for the decay time constant.",
        caveats="As for the half-decay. It equals τ only when the decay is a single exponential from the peak on.",
        example='63.2 ms: 20 × (1 − 1/e) = 12.6 frames from the peak to 18.4 %.'
    ),
    "area": dict(
        formula="sum of the response over the stretch × frame interval in seconds",
        method="The unsmoothed response is summed from the start of the stretch (the stimulus, or the start of the "
               "peak window if that is earlier) to the last frame of the peak window, in percent × seconds.",
        empty="Only for the reasons every kinetic measure can be empty (see 'Stretch' above).",
        meaning="With a linear sensor, total release × how long it stays (clearance time constant); it does not depend "
                "on the sensor's own speed.",
        caveats="Depends on the length of the peak window: a window that ends before the response has decayed cuts the "
                "area short. Baseline drift adds to it in proportion to the window length.",
        example='3.75 %·s: ½ × 50 % × 30 frames × 5 ms.'
    ),
    "signal-to-noise": dict(
        formula="peak of the smoothed response ÷ standard deviation of the unsmoothed response over the baseline window",
        method="The standard deviation is the population SD (divided by n) of the response over the frames of the "
               "pulse's baseline window.",
        empty="The baseline window is shorter than two frames.",
        meaning="How clearly the pulse stands out from the noise of the recording; a quality measure.",
        caveats="Not a biological measure. The peak comes from the smoothed response and the noise from the "
                "unsmoothed one, so smoothing over more frames lowers it slightly while the noise stays the same.",
        example='100: 50 % ÷ 0.5 %.'
    ),
}

SPATIAL_DETAILS = {
    "footprint width": dict(
        formula="λ of a ÷ (1 + (r ÷ λ)²) + c, fitted by least squares to the ring averages against the ring radius r",
        method="Fitted to every ring with an average (out to the largest ring), starting from a = the first ring, "
               "λ = 300 µm, c = 0, with a between 0 and 1000, λ between 10 and 5000 µm and c between −100 and 100. "
               "λ is the distance at which the curve is half-way between its centre and its offset c.",
        empty="Fewer than 8 rings with an average, a first ring that is not above 0, a fit that does not converge, or "
              "a λ at its bounds (not between 11 and 4999 µm).",
        meaning="How far the response reaches from the ROI centre. At 16 µm per pixel this is set by which axons the "
                "stimulus recruits and by light scattered in the slice, not by diffusion, which moves dopamine only "
                "a few tens of µm in the time of a response.",
        caveats="The rings are centred on the ROI centre, not on the electrode tip. A saturated sensor flattens the "
                "centre and widens the apparent footprint. Blur from scattering widens it too.",
        example='The Lorentzian map 50 ÷ (1 + (r ÷ 300 µm)²) %: 300 µm.'
    ),
    "footprint half-width": dict(
        formula="the distance at which the ring averages first fall below half of the largest of the first three",
        method="Going outwards ring by ring within the integration radius, the first ring below half is found and "
               "the crossing is placed between it and the ring before by straight-line interpolation of the ring "
               "averages against the ring radii.",
        empty="A ring within the integration radius has no average, the first ring is not above 0, or no ring within "
              "the integration radius falls below half.",
        meaning="A model-free footprint size: for an exact Lorentzian without offset it equals λ.",
        caveats="Uses the first three rings for the centre, so a centre made noisy by the electrode or by few pixels "
                "moves it. An offset c (a response spread over the whole field) raises the half level.",
        example='The same Lorentzian map: 300 µm.'
    ),
    "r50": dict(
        formula="the radius r at which Σ (ring average⁺ × 2π r_k) over the rings up to r reaches half of the same sum "
                "over all rings within the integration radius",
        method="Ring averages are clipped at 0 (⁺) and weighted by the circumference of the ring at its middle, "
               "r_k = (k + 0.5) × pixel size. The cumulative share is interpolated linearly against r_k to 0.5.",
        empty="A ring within the integration radius has no average, or the first ring is not above 0.",
        meaning="The radius that holds half of the response, summed over the area.",
        caveats="A Lorentzian's area does not converge: r50 depends on the integration radius, and for a true "
                "Lorentzian r50 and the tail fraction are fixed functions of λ. They add information only where the "
                "shape departs from a Lorentzian. Keep the integration radius the same in every analysis that is "
                "compared.",
        example='The same Lorentzian map, integration radius 640 µm: 341 µm.'
    ),
    "tail fraction": dict(
        formula="Σ (ring average⁺ × 2π r_k) over the rings from the tail radius to the integration radius ÷ the same "
                "over all rings within the integration radius",
        method="As for r50; the tail starts at ring round(tail radius ÷ pixel size).",
        empty="As for r50.",
        meaning="The share of the response that lies far from the centre.",
        caveats="As for r50. Noise and bleaching residuals in the outer rings add to the tail.",
        example='The same Lorentzian map, tail beyond 320 µm within 640 µm: 0.56.'
    ),
    "centroid offset": dict(
        formula="distance from the ROI centre to (Σ w·x ÷ Σ w, Σ w·y ÷ Σ w) × pixel size",
        method="The weights w are the response map clipped at 0, within the region radius, with each electrode pixel "
               "replaced by the average of the visible pixels of its ring (so the electrode's shadow does not push "
               "the centroid away).",
        empty="No positive response within the region radius.",
        meaning="How far the centre of mass of the response is from the ROI centre: release that is lopsided around "
                "the ROI.",
        caveats="Noise alone gives an offset above 0 (about σ × √(π/2) for a centroid with scatter σ in each "
                "direction), larger for small responses. A trend with current can therefore be a noise effect.",
        example="A Gaussian spot (SD 8 pixels) whose centre is 10 pixels (160 µm) from the ROI centre: 156 µm, a little less because the region radius (480 µm) cuts off the spot's far edge."
    ),
    "elongation": dict(
        formula="√(largest ÷ smallest eigenvalue of the weighted second moments about the centroid)",
        method="With the weights of the centroid, the 2 × 2 matrix of Σ w·dx², Σ w·dx·dy, Σ w·dy² (divided by Σ w) is "
               "formed, dx and dy being distances from the centroid; the ratio of its eigenvalues gives the ratio of "
               "the spreads along the longest and the shortest axis.",
        empty="No positive response within the region radius, or a smallest spread of 0.",
        meaning="1 for a round footprint, 2 for one twice as long as it is wide: release stretched along a direction, "
                "for example along fibre bundles or the electrode.",
        caveats="Noise makes it slightly above 1 even for a round footprint. The region radius cuts a footprint wider "
                "than the region short, which lowers it. The electrode is filled by ring averages, which makes it "
                "rounder there.",
        example='A Gaussian spot with SDs of 12 and 6 pixels, region radius 960 µm: 2.0.'
    ),
    "heterogeneity": dict(
        formula="√(max(var(map − ring model) − var(noise map − its ring model), 0)) ÷ mean of the map",
        method="Over the visible pixels within the region radius. The ring model gives every pixel the average of its "
               "ring. The noise map is made like the response map from the first frames of the pulse's baseline "
               "window, so it holds the noise and no response; its variance is subtracted.",
        empty="No visible pixel within the region radius, or a mean response that is not above 0.",
        meaning="How patchy the response is around its ring averages, as a fraction of the mean response, with the "
                "patchiness of the noise taken out.",
        caveats="Sensitive to the smoothing and to the region radius. Patches at 16 µm per pixel are groups of many "
                "release sites, not single sites.",
        example='A smooth Lorentzian map without noise: 0.014, which comes from the rings being made of whole pixels: the floor of this measure.'
    ),
    "hot spots": dict(
        formula="number of local maxima of (map − ring model) higher than 3 × SD of (noise map − its ring model) ÷ "
                "visible area in mm²",
        method="A local maximum is a visible pixel equal to the maximum of its 5 × 5 neighbourhood. Only pixels within "
               "the region radius and off the electrode count, for the maxima and for the area.",
        empty="No visible pixel within the region radius, or a mean response that is not above 0.",
        meaning="How many patches stand clearly above their ring.",
        caveats="Single release sites are about 2-3 µm across; at 16 µm per pixel a hot spot is a patch of many. The "
                "count depends on the smoothing and on the noise, and is low for small responses.",
    ),
    "latency slope": dict(
        formula="Theil–Sen slope of the median half-rise latency of each ring against its distance (k × pixel size), "
                "in ms per mm",
        method="Each pixel's response over the stretch is smoothed (3-frame running mean, then a Gaussian of 1.5 "
               "pixels). A pixel counts if its peak is more than 10 SDs of its baseline response and at least 30 % of "
               "the 99.9th percentile of all pixels' peaks, and it is off the electrode. Its half-rise latency is the "
               "time after the stimulus at which its response, going back from its peak, falls to half of the peak "
               "(interpolated between frames). Rings out to the end of the far band with enough counted pixels "
               "(at least 3, and at least 30 % of the ring) get the median latency of their pixels.",
        empty="No stimulus frame, or fewer than 10 rings with a median latency.",
        meaning="Whether release starts later far from the centre: a positive slope is a wave travelling outwards.",
        caveats="Differences are a few ms, near the frame interval. A camera with a rolling shutter records rows at "
                "slightly different times, which can mimic or hide a slope along the image's vertical axis.",
        example='Release that starts 1 frame (5 ms) later for every 4 pixels (64 µm) from the centre: 78 ms/mm.'
    ),
    "far-near delay": dict(
        formula="mean of the ring median latencies in the far band − the same in the near band",
        method="As for the latency slope. A ring is in a band when k × pixel size is within the band.",
        empty="No ring in the near or the far band has a median latency.",
        meaning="How much later release starts far from the centre.",
        caveats="As for the latency slope.",
        example="The same wave: 33.5 ms, the far band's rings being on average about 0.43 mm further out than the near band's."
    ),
    "far-near decay ratio": dict(
        formula="t50 of the far band ÷ t50 of the near band, both times after the peak frame",
        method="Each band's curve is the mean of its rings' averages in every bin; t50 is the time at which the curve "
               "first falls to half of its value in the first bin, interpolated linearly between bins.",
        empty="Either band does not fall to half within the stretch followed, or the near band is not above 0 in the "
              "first bin.",
        meaning="Whether the response far from the centre fades faster (below 1) or slower (above 1) than near it. "
                "Below 1 the footprint narrows as it decays: its width λ changes at d ln λ/dt ≈ −(1/τ(λ) − 1/τ(0)), "
                "τ(r) being the decay time constant at distance r (derived).",
        caveats="Both times include the time from the peak frame to the first bin. A saturated sensor and "
                "saturable uptake both make the centre, where the response is largest, fade more slowly: compare "
                "responses of similar size. A slow sensor makes every ring decay at its own off-rate and pulls the "
                "ratio towards 1. Bleaching left in the trace makes the far band (smaller) fade faster; use an "
                "unstimulated partner.",
        example='A response whose decay time constant falls from 40 frames at the centre by 10 frames per 640 µm (5 ms frames, response map from the peak frame on): 0.84.'
    ),
    "decay-distance slope": dict(
        formula="Theil–Sen slope of t50 of each ring against its distance (k × pixel size), in ms per mm",
        method="Every ring out to the end of the far band gets the t50 of its own average over the bins, found as for "
               "the bands.",
        empty="Fewer than 10 rings whose average falls to half within the stretch followed.",
        meaning="How the decay time changes with distance from the centre: negative when far rings fade faster.",
        caveats="As for the far-near decay ratio. Single rings are noisier than bands.",
        example='The same response: −54 ms/mm, that is −10 frames ÷ 640 µm × ln 2 × 5 ms.'
    ),
}

NEAR_TO_FAR_DETAILS = dict(
    formula="(far-band mean of map A ÷ far-band mean of map B) ÷ (near-band mean of map A ÷ near-band mean of map B)",
    method="Map A is the response map of the comparison's pulse, map B that of the pulse it is relative to. The band "
           "means are means of the ring averages of the rings in the band.",
    empty="Map B's band mean is 1 (% or percentage point) or less in either band, or either pulse cannot be mapped.",
    meaning="Whether the comparison (for example the paired-pulse ratio) is lower far from the centre (below 1) than "
            "near it.",
    caveats="Small responses in the far band make it noisy; the 1 % limit keeps out bands with almost no response.",
    example="P1's map 40 % everywhere, P2's map 20 % within 200 µm of the centre and 10 % beyond: P2 ÷ P1 is 0.5 near "
            "and 0.25 far, so the near-to-far index of PPR is 0.5.",
)
