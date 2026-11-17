Choosing spontaneous measures
=============================

Typical values
--------------

With the Standard detector, 1,570 unstimulated recordings of the lab
(178.9 min searched) gave 1,236 events. Typical values (median, with the
middle half in brackets), for comparison with your own:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Measure
     - Typical value
   * - rate
     - 6.9 per min per 2 mm field (paired-pulse folders 6.2, 11-pulse
       folders 7.3)
   * - density
     - 1.55–1.81 per min·mm²
   * - fitted peak
     - 2.95 % (2.12–4.83)
   * - width
     - 158 µm (130–188)
   * - half-maximum area
     - 0.109 mm² (0.074–0.154)
   * - size
     - 0.51 %·mm² (0.28–0.92)
   * - rise 10-90
     - 29 ms (24–48)
   * - half-decay
     - 102 ms (63–150)
   * - distance to the ROI centre
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
the estimate of false alarms (see :term:`sign-flipped`).

**Amplitude: use the fitted peak**, not the local peak, which is lowered by
pooling. The fitted peak needs a good fit, which about 60 % of events have.

**Width, half-maximum area and size** describe how far the released
dopamine spreads. They come from the same fit and are empty for the same
events as the fitted peak. Size, the peak times the area, is in the units
of an evoked response integrated over the slice, so the two can be
compared: one event is about 1–2 % of a 50 µA pulse.

**Rise and half-decay** come from the :term:`pooled trace`. Dim events give
noisier traces, which read shorter times, so compare groups whose events
have similar peaks, or compare medians over many events. The *decay tau* is
less sensitive to noise near the half level.

**Place.** Events need not be concentrated at the :term:`ROI centre`, and
they can lean towards the electrode's side of the field. The *share near
the ROI centre* and the *share on the electrode side* track this per slice.
Compare them with the share of tissue near the centre or on that side,
which depends on where the centre lies in the image.

More measures
-------------

These are built from the same events and are described in full in
:doc:`measure_reference`. Try them on your own data before relying on them.

* **Time course:** *time to peak*, *rise speed*, *half-width*, *decay tau*,
  *area* of the pooled trace.
* **Place:** *x*, *y*, *electrode side*.
* **Clustering:** *nearest-neighbour distance* and the *clustering index*
  (below 1 when events come back to the same places more often than
  chance); the number of *recurring sites* and the *share at recurring
  sites*.
* **Timing:** the *share together*, for bursts. Expect about a fifth of
  events to have a neighbour within 1 s at 7 events per minute by chance
  alone.
* **Budget:** *release per minute*, the slice's rate × its median event
  size, in the units of an evoked response integrated over the slice.
* **Noise:** *pixel noise*, to check that groups are equally noisy. Noisier
  slices hide dim events, so they can show fewer events at the same
  release.

What to watch
-------------

* **Recording time.** Rates can change over a recording day; in the lab's
  recordings they were lower in the first hour. Compare slices recorded at
  similar times, or note when each was recorded.
* **Saturation.** Above about 45 events per minute (as after
  :term:`4-AP`), nearby events can merge into one region, so counts may be
  low.
