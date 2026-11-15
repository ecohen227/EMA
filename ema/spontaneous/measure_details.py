"""The full description of every spontaneous-event measure, for the documentation's measure reference.

One entry per measure key of measures.py (EVENT, RECORDING, SLICE): its
formula, how it is computed, when it is empty, what it reflects and what
to be careful of. A test requires an entry, with every field, for every
measure. Italic names are settings (see the detector's settings).
"""

PEAK_MAP = (
    "The peak map: the dF/F movie minus each pixel's mean over frames 45 to 15 before the onset, blurred with a Gaussian of "
    "1 pixel; within frames 5 before to 40 after the onset, the frame where the mean of the pixels within 48 µm of the event's "
    "maximum (smoothed over 5 frames) is highest is found in the first 35, and the map is the mean of 3 frames before it to 4 "
    "after it; the median of the tissue farther than 480 µm is subtracted. A Gaussian peak·exp(−r²/2σ²) + offset is fitted to "
    "the map's tissue pixels within *Fit the width within* (400 µm) by least squares, with peak 0–100 %, σ 8–400 µm, offset "
    "±5 % and the centre at most 128 µm from the maximum."
)
GOOD_FIT = ("Empty when the fit failed, when fewer than 200 tissue pixels lie within the fit radius, when the event is closer than "
            "45 frames to the start of the searched movie or 40 frames to its end, or when the fit is not good: fit quality below "
            "*Smallest fit quality* (0.2), σ at or above *Largest width* (380 µm), or a peak of 0.")
TRACE = (
    "The pooled trace: the dF/F movie from 60 frames before the onset to 200 after, through the detector's spatial filter "
    "(and minus each frame's tissue median, if the field-wide signal is removed), at the event's maximum; taken relative to "
    "its median up to 10 frames before the onset and smoothed over 3 frames. Its peak is the largest value from 10 frames "
    "before the onset to 80 after."
)
TRACE_EMPTY = ("Empty when the event is closer than 60 frames to the start of the searched movie or 200 to its end, or when the "
               "pooled trace has no peak above 0.")
POOLED = ("The pooled trace is an average over about a 128 µm Gaussian, so its peak is lower than the event's own (diluted); "
          "use the fitted peak for amplitude. A dim event's trace is noisier, which tends to shorten its measured times.")

EVENT_DETAILS = {
    "onset": dict(
        formula="(onset frame) × frame interval ÷ 1000",
        method="The onset frame is the frame of the region's largest z, where the template's onset lies; frames are counted "
               "from the start of the recording (its frame 0 is the second frame of the file).",
        empty="Never.",
        meaning="When the event happened, for timing measures and to find it in the movie.",
        caveats="The onset is the template's best alignment, within a few frames of the visible start.",
    ),
    "z": dict(
        formula="max over the region of (filter output − its median) ÷ (1.4826 × its median absolute deviation)",
        method="See the detector's steps 2 to 6: the largest z of the event's connected region of z ≥ *Region threshold*.",
        empty="Never.",
        meaning="How far the event stands out of that pixel's noise, after pooling: a larger z is a clearer event.",
        caveats="z grows with an event's peak, width and duration together, and with how quiet the slice is; it is a "
                "detection score, not a size.",
    ),
    "fitted peak": dict(
        formula="100 × peak of the fitted Gaussian",
        method=PEAK_MAP,
        empty=GOOD_FIT,
        meaning="How much the sensor's fluorescence rose at the event's centre: the best estimate of its amplitude.",
        caveats="Real events are not exactly Gaussian; an irregular event's fitted peak is an average shape's peak.",
    ),
    "width": dict(
        formula="σ of the fitted Gaussian × pixel size",
        method=PEAK_MAP,
        empty=GOOD_FIT,
        meaning="How far the released dopamine spread: the radius at which the event falls to 61 % of its peak.",
        caveats="The map is blurred by 1 pixel (16 µm), which widens very narrow events slightly; events narrower than about "
                "48 µm are rarely detected at all.",
    ),
    "full width at half maximum": dict(
        formula="2·√(2·ln 2) × width ≈ 2.355 × width",
        method="From the fitted width.",
        empty=GOOD_FIT,
        meaning="The diameter within which the event is above half its peak: the event's visible size.",
        caveats="As for the width.",
    ),
    "half-maximum area": dict(
        formula="π × (√(2·ln 2) × width)², in mm²",
        method="From the fitted width.",
        empty=GOOD_FIT,
        meaning="The area of slice the event covers at half its peak or more.",
        caveats="As for the width.",
    ),
    "size": dict(
        formula="fitted peak × 2π × width², with the width in mm",
        method="The volume under the fitted Gaussian: its dF/F integrated over the slice.",
        empty=GOOD_FIT,
        meaning="The amount of dopamine signal one event releases, in the same units as an evoked response integrated over "
                "the slice, so the two can be compared (one event is about 1–2 % of a 50 µA pulse in the study).",
        caveats="It multiplies two fitted numbers, so their errors add up; compare medians of many events.",
    ),
    "fit quality": dict(
        formula="1 − Σ(map − fit)² ÷ Σ(map − mean of map)², over the fitted pixels",
        method=PEAK_MAP,
        empty="Empty when the fit failed or could not be made (see the fitted peak).",
        meaning="How well a round Gaussian describes the event: low values are irregular or very faint events.",
        caveats="It is computed over the whole fit radius, so a small event on a large window has a lower r² than a large "
                "one of the same clarity.",
    ),
    "local peak": dict(
        formula="100 × peak of the pooled trace",
        method=TRACE,
        empty=TRACE_EMPTY,
        meaning="The peak as the detector sees it, pooled over space.",
        caveats=POOLED,
    ),
    "time to peak": dict(
        formula="(frame of the pooled trace's peak − onset frame) × frame interval",
        method=TRACE,
        empty=TRACE_EMPTY,
        meaning="How long after its detected onset the event peaks.",
        caveats="Can be negative when the peak is found up to 10 frames before the onset. " + POOLED,
    ),
    "rise 10-90": dict(
        formula="(last frame below 90 % of the peak − last frame below 10 % of the peak, both before the peak) × frame interval",
        method=TRACE + " Frames, not interpolated, as in the study.",
        empty=TRACE_EMPTY + " Also empty when the trace does not cross both levels before its peak.",
        meaning="How fast the event rises: with a ~5 ms frame interval, typical events rise in about 25–50 ms.",
        caveats="Whole frames only (steps of 4.8 ms). " + POOLED,
    ),
    "rise speed": dict(
        formula="0.8 × local peak ÷ (rise 10-90 in s)",
        method="From the local peak and the 10–90 % rise time.",
        empty="Empty when the rise time is empty.",
        meaning="How steep the rise is, in % dF/F per second: release that is both large and fast is steep.",
        caveats="Uses the diluted local peak. " + POOLED,
    ),
    "half-width": dict(
        formula="(first frame below half the peak after it − last frame below half before it) × frame interval",
        method=TRACE,
        empty=TRACE_EMPTY + " Also empty when the trace does not fall below half its peak, before or after it.",
        meaning="How long the event lasts at half its height.",
        caveats="Whole frames only. " + POOLED,
    ),
    "half-decay": dict(
        formula="(first frame after the peak below half the peak − the peak's frame) × frame interval",
        method=TRACE + " As in the study.",
        empty=TRACE_EMPTY + " Also empty when the trace does not fall below half its peak within the 200 frames after the onset.",
        meaning="How fast the dopamine signal is cleared or the sensor unbinds.",
        caveats="Noise makes a dim event's trace fall below half earlier, so dimmer events read shorter half-decays. " + POOLED,
    ),
    "decay tau": dict(
        formula="τ of a·exp(−t/τ) + c, fitted by least squares to the pooled trace over the 80 frames from its peak",
        method=TRACE + " Bounds: τ from 0.5 frame to 5000 frames; a result at a bound is left empty.",
        empty=TRACE_EMPTY + " Also empty when the fit fails or stops at a bound.",
        meaning="The decay as a time constant, less sensitive to noise near the half level than the half-decay.",
        caveats="An event followed by another within 0.4 s is fitted over both. " + POOLED,
    ),
    "area": dict(
        formula="Σ pooled trace from the frame after its last frame below 10 % before the peak to the first frame below 10 % "
                "after it × frame interval ÷ 1000, in %·s",
        method=TRACE + " If the trace never falls below 10 % after the peak, the sum runs to the end of the trace.",
        empty=TRACE_EMPTY + " Also empty when the trace does not start below 10 % of its peak.",
        meaning="The event's whole time course in one number: amplitude and duration together.",
        caveats=POOLED,
    ),
    "x": dict(
        formula="column of the event's centre × pixel size",
        method="The centre of the fitted Gaussian when the fit is good, otherwise the pixel of the region's largest z.",
        empty="Never.",
        meaning="Where the event was, from the left edge of the image.",
        caveats="With a poor fit the position is the z maximum, which can be up to a few pixels off the visible centre.",
    ),
    "y": dict(
        formula="row of the event's centre × pixel size",
        method="As for x.",
        empty="Never.",
        meaning="Where the event was, from the top edge of the image.",
        caveats="As for x.",
    ),
    "distance to the release centre": dict(
        formula="√((x − ROI centre x)² + (y − ROI centre y)²)",
        method="The release centre of the recording's folder: its ROI centre in the ROI file, or else found automatically "
               "from the folder's stimulated recordings, as in ROI Selection (the centre of evoked release).",
        empty="Empty when the folder has no release centre: no ROI file entry and no stimulated recording.",
        meaning="Whether spontaneous events happen where evoked release is strongest, or anywhere.",
        caveats="Compare with the distances of the tissue itself: most of a 2 mm field lies far from its centre.",
    ),
    "distance to the electrode": dict(
        formula="distance from the pixel of the region's largest z to the nearest electrode pixel × pixel size",
        method="The electrode mask of the folder: from the ROI file, or else found automatically from its stimulated "
               "recordings, as in ROI Selection.",
        empty="Empty when the folder has no electrode mask.",
        meaning="Whether events crowd near the stimulating electrode, for example because of damage or leakage there.",
        caveats="Measured from the z maximum (as in the study), not from the fitted centre.",
    ),
    "electrode side": dict(
        formula="1 if (event centre − release centre) · (electrode's mean pixel − release centre) > 0, else 0",
        method="The electrode's mean pixel gives the side it comes from.",
        empty="Empty when the folder has no electrode mask or no release centre.",
        meaning="With the share per slice: whether events lean towards the electrode's side of the field.",
        caveats="The release centre is usually not in the middle of the image, so the two sides have different areas; "
                "compare with the share of tissue on each side.",
    ),
}

RECORDING_DETAILS = {
    "events": dict(
        formula="number of regions reaching θ, without echoes, with their onset not in the end trim",
        method="See the detector's steps.",
        empty="Never.",
        meaning="How many spontaneous events the recording holds.",
        caveats="Depends on the searched time; compare rates.",
    ),
    "searched time": dict(
        formula="(frames of the filtered movie − frames of the end trim) × frame interval",
        method="The filtered movie has (frames searched − template length + 1) frames, since the template must fit; the end "
               "trim is *Leave out onsets in the last*. About 6.8 s for a 1,650-frame recording with the defaults.",
        empty="Never.",
        meaning="The time in which an onset could be counted: the denominator of every rate.",
        caveats="Shorter than the recording: the frames left out at both ends, the template's length and the end trim.",
    ),
    "rate": dict(
        formula="events ÷ (searched time in min)",
        method="From the two above.",
        empty="Empty when nothing was searched.",
        meaning="How often spontaneous events happen in the field.",
        caveats="One recording holds a few events at most; per-slice rates pool several recordings and are steadier.",
    ),
    "tissue area": dict(
        formula="tissue pixels × (pixel size in mm)²",
        method="The tissue mask: blocks bright enough and mostly off the electrode (see the settings under Tissue).",
        empty="Never.",
        meaning="How much slice was searched, for densities.",
        caveats="Tissue at the image edge counts fully, though events there are only partly in view.",
    ),
    "density": dict(
        formula="rate ÷ tissue area",
        method="From the two above.",
        empty="Empty when nothing was searched or no tissue was found.",
        meaning="Events per minute per mm² of tissue: comparable between fields of different sizes.",
        caveats="As for the rate.",
    ),
    "sign-flipped": dict(
        formula="number of events found in −dF/F (dips), counted like the events",
        method="The same z movie with its sign flipped; the echo rule is applied both ways, so the control stays fair.",
        empty="Empty when *Count sign-flipped detections* is off.",
        meaning="An estimate of the false positives: noise produces dips as often as rises, events do not.",
        caveats="Includes genuine negative transients and artefacts (bubbles, debris), so it overestimates the false "
                "positives slightly.",
    ),
    "time-reversed": dict(
        formula="number of events found in the movie played backwards",
        method="The dF/F movie is reversed in time and searched again with every step.",
        empty="Empty when *Count time-reversed detections* is off.",
        meaning="A shape test: a real event (fast rise, slow decay) looks wrong backwards and is mostly not found.",
        caveats="A strong event can still be found reversed, since its reversed shape keeps about three-quarters of its score.",
    ),
    "pixel noise": dict(
        formula="median over the tissue pixels of 1.4826 × median(abs(dF/F − median dF/F)) over frames, × 100",
        method="On the bleaching-corrected dF/F movie, before the spike filter (which would lower white noise by about a "
               "third) and before any other filtering.",
        empty="Empty when no tissue was found.",
        meaning="How noisy single pixels are (4–6 % per frame in the study): noisier slices hide dim events.",
        caveats="Events themselves barely change it: they occupy few frames.",
    ),
}

SLICE_DETAILS = {
    "events": dict(formula="Σ events over the slice's recordings", method="All searched recordings of the folder.",
                   empty="Never.", meaning="How many events the slice gave.", caveats="Depends on how long it was recorded."),
    "searched time": dict(formula="Σ searched time ÷ 60", method="All searched recordings.", empty="Never.",
                          meaning="The slice's total searched time, in minutes.", caveats="—"),
    "rate": dict(formula="Σ events ÷ Σ searched time", method="Pooled over the recordings, not a mean of their rates.",
                 empty="Empty when nothing was searched.", meaning="The slice's rate of spontaneous events.",
                 caveats="Recording time and order matter: the study found rates rise over the first hour of a day."),
    "density": dict(formula="rate ÷ mean tissue area of the recordings", method="From the rate and the recordings' tissue areas.",
                    empty="Empty when nothing was searched.", meaning="Events per minute per mm² of tissue.",
                    caveats="As for the rate."),
    "sign-flipped rate": dict(formula="Σ sign-flipped ÷ Σ searched time", method="Pooled over the recordings.",
                              empty="Empty when the control is off or nothing was searched.",
                              meaning="The false-positive rate estimate.", caveats="See the recordings' sign-flipped count."),
    "time-reversed rate": dict(formula="Σ time-reversed ÷ Σ searched time", method="Pooled over the recordings.",
                               empty="Empty when the control is off or nothing was searched.",
                               meaning="The shape-test rate.", caveats="See the recordings' time-reversed count."),
    "rate above the sign-flip floor": dict(
        formula="(Σ events − Σ sign-flipped) ÷ Σ searched time", method="Pooled over the recordings.",
        empty="Empty when the control is off or nothing was searched.",
        meaning="The rate of events in excess of the false-positive estimate.",
        caveats="Can be negative in a quiet slice; it is an estimate, not a count."),
    "sign-flipped share": dict(formula="Σ sign-flipped ÷ Σ events", method="Pooled over the recordings.",
                               empty="Empty when the control is off or no event was found.",
                               meaning="The share of the slice's events that noise alone could explain (7 % in the study).",
                               caveats="Unstable when the slice has few events."),
    "share near the release centre": dict(
        formula="(events with distance to the release centre < *Near the release centre within*) ÷ events",
        method="Over the events with a distance to the release centre.",
        empty="Empty when no event was found, or the folder has no release centre.",
        meaning="Whether events concentrate where evoked release is strongest (11 % within 480 µm in the study, against "
                "17 % of the tissue).",
        caveats="Compare with the share of tissue within the same distance, which depends on where the centre lies."),
    "share on the electrode side": dict(
        formula="mean of the events' electrode side", method="Over the events with an electrode side.",
        empty="Empty when no event has an electrode side.",
        meaning="Whether events lean towards the electrode's side (77 % in the study, against about half the field).",
        caveats="See the electrode side."),
    "nearest-neighbour distance": dict(
        formula="median over events of the distance to the nearest other event of the slice",
        method="Events of all recordings of the slice together, by their centres.", empty="Empty with fewer than 2 events.",
        meaning="How close together the slice's events are.",
        caveats="Shrinks with more events, so compare the clustering index between slices."),
    "clustering index": dict(
        formula="nearest-neighbour distance ÷ mean over 200 draws of the same for as many random tissue pixels",
        method="Random pixels from the first searched recording's tissue, with a fixed seed, so the number is repeatable.",
        empty="Empty with fewer than 2 events.",
        meaning="Below 1: events come back to the same places more than chance (hot spots); about 1: no preference.",
        caveats="Few events give a noisy ratio; the study's matched-partner test found recurring sites closer than chance "
                "(840 against 1,057 µm)."),
    "recurring sites": dict(
        formula="number of groups of 2 or more events linked by distances below *Same site within*",
        method="Events closer than the radius join one site, directly or through other events.",
        empty="Empty when no event was found.", meaning="How many places released more than once.",
        caveats="Depends on the number of events and the radius."),
    "share at recurring sites": dict(formula="events at a recurring site ÷ events", method="See recurring sites.",
                                     empty="Empty when no event was found.",
                                     meaning="How much of the slice's activity comes from places that release again.",
                                     caveats="As for recurring sites."),
    "share together": dict(
        formula="(events with another event of the same recording within *Together within*) ÷ events",
        method="Onsets within each recording.", empty="Empty when no event was found.",
        meaning="Whether events come in bursts rather than one at a time.",
        caveats="Rises with the rate by chance alone: at 7 events per minute, about a fifth of events have a neighbour "
                "within 1 s at random."),
    "release per minute": dict(
        formula="rate × median size of the slice's events, in %·mm² per minute",
        method="Over the events with a size.", empty="Empty when no event has a size.",
        meaning="The spontaneous signal per minute, comparable with an evoked response integrated over the slice (about "
                "16 % of a 50 µA pulse per minute in the study).",
        caveats="A product of a rate and a median, both uncertain in a quiet slice."),
}

SUMMARY = dict(
    formula="median, mean, smallest or largest of an event measure over the slice's events",
    method="Over all events of all searched recordings of the slice; empty values are left out.",
    empty="Empty when no event of the slice has the measure.",
    meaning="The slice's typical event.",
    caveats="A slice with one or two events gives an unstable median.",
)
