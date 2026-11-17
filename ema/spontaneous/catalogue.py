"""The catalogue of spontaneous-event measures: per event, per recording and per slice.

Every measure is described once here, with its full description in
measure_details.py. The configurator's check lists, the tables and the
documentation are all built from these lists; the measures are computed in
measures.py. To add a measure, see "Extending EMA" in the documentation.
"""

from ..definitions import Measure

EVENT = [
    Measure("onset", "s", "Detection", "The time of the event's onset from the start of the recording."),
    Measure("strength", "× noise", "Detection", "How many times the noise level the event rose, after filtering: its "
                                                "detection score."),
    Measure("fitted peak", "%", "Size", "The peak dF/F of the Gaussian fitted to the event's peak map."),
    Measure("width", "µm", "Size", "σ of the Gaussian fitted to the event's peak map: its radius at 61 % of the peak."),
    Measure("full width at half maximum", "µm", "Size", "2.355 × width: the diameter at which the event is half its peak."),
    Measure("half-maximum area", "mm²", "Size", "The area within which the fitted Gaussian is above half its peak."),
    Measure("size", "%·mm²", "Size", "fitted peak × 2π × width²: the dF/F integrated over the slice, like an evoked total."),
    Measure("fit quality", "r²", "Size", "The share of the peak map's variance the fitted Gaussian explains."),
    Measure("local peak", "%", "Time course", "The peak of the event's pooled trace (lowered by the pooling)."),
    Measure("time to peak", "ms", "Time course", "From the detected onset to the peak of the pooled trace."),
    Measure("rise 10-90", "ms", "Time course", "Time from 10 % to 90 % of the peak on the pooled trace."),
    Measure("rise speed", "%/s", "Time course", "80 % of the local peak ÷ the 10–90 % rise time."),
    Measure("half-width", "ms", "Time course", "How long the pooled trace stays above half its peak."),
    Measure("half-decay", "ms", "Time course", "From the peak to the first frame below half the peak."),
    Measure("decay tau", "ms", "Time course", "τ of an exponential fitted to the pooled trace from its peak on."),
    Measure("area", "%·s", "Time course", "The pooled trace integrated from 10 % of the peak on the rise to 10 % on the decay."),
    Measure("x", "µm", "Position", "The event's centre from the left edge of the image."),
    Measure("y", "µm", "Position", "The event's centre from the top edge of the image."),
    Measure("distance to the ROI centre", "µm", "Position", "From the event's centre to the ROI centre."),
    Measure("distance to the electrode", "µm", "Position", "From the event's strongest pixel to the nearest pixel of the electrode."),
    Measure("electrode side", "yes = 1", "Position", "1 when the event lies on the electrode's side of the ROI centre."),
]

RECORDING = [
    Measure("events", "", "Counts", "The events found in the recording."),
    Measure("searched time", "s", "Counts", "The time in which onsets are counted."),
    Measure("rate", "per min", "Counts", "events ÷ searched time."),
    Measure("tissue area", "mm²", "Counts", "The area searched: the tissue, without the electrode."),
    Measure("density", "per min·mm²", "Counts", "rate ÷ tissue area."),
    Measure("sign-flipped", "", "Controls", "Events found in the movie turned upside down (dips): an estimate of the "
                                           "false alarms."),
    Measure("time-reversed", "", "Controls", "Events found in the movie played backwards: a test of the events' shape."),
    Measure("pixel noise", "%", "Controls", "The median over the tissue of each pixel's robust SD of dF/F."),
]

SLICE = [
    Measure("events", "", "Counts", "The events found in all recordings of the slice."),
    Measure("searched time", "min", "Counts", "The searched time of all recordings of the slice."),
    Measure("rate", "per min", "Counts", "events ÷ searched time."),
    Measure("density", "per min·mm²", "Counts", "rate ÷ the mean tissue area of the recordings."),
    Measure("sign-flipped rate", "per min", "Controls", "Sign-flipped events ÷ searched time."),
    Measure("time-reversed rate", "per min", "Controls", "Time-reversed events ÷ searched time."),
    Measure("rate above the sign-flip floor", "per min", "Controls", "(events − sign-flipped events) ÷ searched time."),
    Measure("sign-flipped share", "fraction", "Controls", "Sign-flipped events ÷ events."),
    Measure("share near the ROI centre", "fraction", "Place", "The share of events within *Near the ROI centre within* of "
                                                               "the ROI centre."),
    Measure("share on the electrode side", "fraction", "Place", "The share of events on the electrode's side of the ROI "
                                                                 "centre."),
    Measure("nearest-neighbour distance", "µm", "Place", "The median distance from each event to the nearest other event of "
                                                         "the slice."),
    Measure("clustering index", "ratio", "Place", "Nearest-neighbour distance ÷ the same for as many random points on the "
                                                  "tissue."),
    Measure("recurring sites", "", "Place", "Places with two or more events, events closer than *Same site within* being one "
                                            "place."),
    Measure("share at recurring sites", "fraction", "Place", "The share of events at a recurring site."),
    Measure("share together", "fraction", "Time", "The share of events with another event of the same recording within "
                                                  "*Together within*."),
    Measure("release per minute", "%·mm² per min", "Time", "rate × the median size of the slice's events."),
]

STATISTICS = ("median", "mean", "min", "max")  # how event measures are summarised per slice
EVENT_KEYS = [m.key for m in EVENT]
RECORDING_KEYS = [m.key for m in RECORDING]
SLICE_KEYS = [m.key for m in SLICE]

# Keys renamed since earlier detector files were saved: old key -> new key.
RENAMED = {"z": "strength", "distance to the release centre": "distance to the ROI centre",
           "share near the release centre": "share near the ROI centre"}
