Choosing measures
=================

What the study's numbers were
-----------------------------

With *Detector v5*, on 1,570 unstimulated recordings (178.9 min searched),
the study found 1,236 events. Typical values (median, with the middle half
in brackets), for comparison with your own:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Measure
     - Value in the study
   * - rate
     - 6.9 per min per 2 mm field (paired-pulse set 6.2, 11-pulse set 7.3)
   * - density
     - 1.55–1.81 per min·mm²
   * - fitted peak
     - 2.95 % (2.12–4.83)
   * - width (σ)
     - 158 µm (130–188)
   * - half-maximum area
     - 0.109 mm² (0.074–0.154)
   * - size
     - 0.51 %·mm² (0.28–0.92)
   * - rise 10-90
     - 29 ms (24–48)
   * - half-decay
     - 102 ms (63–150)
   * - distance to the release centre
     - 951 µm; to the electrode 610 µm
   * - sign-flipped share
     - 7 %
   * - slices with no event
     - 31 %

Which to rely on
----------------

**Rates and densities** are the most robust: they need only the detection.
Report them with the **sign-flipped rate** (or the *rate above the
sign-flip floor*), so a difference between groups can be checked against
the false-positive estimate. In the study, the IFNγ excess (×1.23) far
exceeded any difference in sign-flipped rates.

**Amplitude: use the fitted peak**, not the local peak, which is diluted by
pooling. The fitted peak needs a good fit (about 60 % of events in the
study).

**Width, half-maximum area and size** describe how far the released
dopamine spreads. They come from the same fit and have the same coverage as
the fitted peak. Size, the peak times the area, is in the units of an evoked
response integrated over the slice, so the two can be compared: one event
was about 1–2 % of a 50 µA pulse.

**Rise and half-decay** come from the pooled trace. Dim events give noisier
traces, which read shorter times, so compare groups whose events have
similar peaks, or compare medians over many events. The *decay tau* is less
sensitive to noise near the half level.

**Place.** Events do not concentrate at the release centre: 11 % lay within
480 µm of it, against 17 % of the tissue. They do lean towards the
electrode's side: 77 % of fitted events, against about half of the field.
The *share near the release centre* and *share on the electrode side* track
this per slice; compare them with the share of tissue, which depends on
where the centre lies in the image.

New measures
------------

These were not in the study. They are built from the same events and are
documented in full in :doc:`measure_reference`; treat them as exploratory
until tried on your data.

* **Time course:** *time to peak*, *rise speed*, *half-width*, *decay tau*,
  *area* of the pooled trace.
* **Place:** *x*, *y*, *electrode side*.
* **Clustering:** *nearest-neighbour distance* and the *clustering index*
  (below 1 when events come back to the same places more than chance); the
  number of *recurring sites* and the *share at recurring sites*. The study
  found recurring events closer than position-matched random partners (840
  against 1,057 µm), so hot spots are plausible.
* **Timing:** the *share together*, for bursts. Expect about a fifth of
  events to have a neighbour within 1 s at 7 events per minute by chance
  alone.
* **Budget:** *release per minute*, the slice's rate × its median event
  size: in the study about 16 % of a 50 µA pulse per minute.
* **Noise:** *pixel noise*, to check that groups are equally noisy. In the
  study, noisier slices had fewer events at the same evoked release.

What to watch
-------------

* **Recording time.** Rates were lower in the first hour of a day (0.47 of
  the animal's average) and steady afterwards. Compare slices recorded at
  similar times, or note when each was recorded.
* **Saturation.** Above about 45 events per minute (as after 4-AP), nearby
  events can merge into one region, so counts may be low.
* **Planted events** are not part of the configurator. The study's
  sensitivity per slice varied only about ±12 %, so one threshold is fair
  across slices and groups.
