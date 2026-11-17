Evoked measure reference
========================

Every number a protocol can produce, one by one: how it is named, its unit,
its definition, its formula, exactly how it is computed, when it is left
empty, what it reflects, what to be careful of, and a worked example.
:doc:`measures` shows the measures on real recordings.

How measures are named
----------------------

* Baselines, pulses, comparisons and fits have the names given in the
  protocol: ``B1``, ``P1``, ``PPR``, ``Tau``.
* What is measured on a pulse is named after it: ``P1 response``,
  ``P1 half-decay``, ``P1 footprint width``.
* A near-to-far index is named after its comparison: ``PPR near-to-far``.
* A slice value is named after the per-recording measure it summarises:
  ``PPR mean``, ``P1 response mean 100-400``, ``B1 spread``; a fit across
  conditions after the fit: ``Recovery time constant``.

An **empty** value means "could not be measured on this recording (or
slice)"; it is never replaced by 0, and slice summaries leave it out.

Units
-----

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Unit
     - Meaning
   * - counts
     - Camera units of brightness, as stored in the TIFF.
   * - %
     - With a brightness trace, a change relative to the baseline
       (dF/F × 100). With a stimulated ÷ unstimulated trace, the trace itself
       is in % of the unstimulated recording's brightness.
   * - percentage points
     - The difference between two values in %: a peak of 33 % and a baseline
       of −1 % differ by 34 percentage points.
   * - ratio, fraction
     - One value divided by another, without a unit; a fraction lies between
       0 and 1.
   * - ms, ms/mm, %/s, %·s, µm, per mm²
     - Times, times per mm of distance, rates, areas under a response,
       distances and densities. Frames are converted to ms with the time
       between frames.

Words used below
----------------

More words are explained in the :doc:`../glossary`.

Time between frames
   Set on the *Recordings* tab (4.849 ms by default). Times measured in
   frames are converted with it.

Response
   The trace as a change from the pulse's baseline, in percent: for a
   brightness trace (trace ÷ baseline − 1) × 100, that is dF/F in percent;
   for a stimulated ÷ unstimulated trace, trace − baseline, in percentage
   points. The baseline is the mean of the trace over the pulse's baseline
   window.

Smoothed response
   The response averaged over a running window of *Smoothing* frames
   (*Kinetics* tab, 3 by default), centred on each frame. 1 means no
   smoothing.

Stretch
   The frames a pulse's kinetic measures look at: from its stimulus (or the
   start of its peak window, if that is earlier) to the last frame of its
   peak window. The peak is the maximum of the smoothed response inside
   the peak window. A level that is not crossed inside the stretch gives an
   empty value. **Every** kinetic measure of a pulse is empty when its
   baseline is empty or 0, when its peak window is not set or starts after
   the end of the recording, or when its smoothed response is not above 0
   at the peak.

Crossing
   The time at which the smoothed response passes a level. It is found by
   walking frame by frame from the peak (back for the rise, forward for the
   decay) to the first frame at or below the level, and placing the crossing
   between that frame and the one before it by straight-line interpolation.

Response map
   For one pulse, the response of every pixel around the peak:

   1. With a bleaching correction (see :doc:`measures`), every pixel is
      first corrected with the same pixel of the unstimulated partner.
   2. Each pixel's response is taken relative to its mean over the pulse's
      baseline window.
   3. The peak is the frame of the maximum of the ROI trace in the pulse's
      peak window. The map averages *Frames before the peak* frames before
      it and *Frames from the peak on* frames from it on (frames peak − 1
      to peak + 3 by default).
   4. The map is blurred with a :term:`Gaussian` of *Spatial smoothing*
      pixels.

Ring
   Ring *k* holds the pixels whose distance from the ROI centre, in pixels,
   rounds down to *k*. Its **average** is the mean of its pixels, leaving
   out the electrode when *Leave out the electrode* is ticked. A ring with
   less than a quarter of its pixels in view (inside the image and off the
   electrode) has no average. Its **radius** is the mean distance of its
   pixels from the centre (about *k* + 0.5 pixels), times the pixel size.

Band
   The near and the far band, set on the *Spatial* tab (0-160 µm and
   400-640 µm by default). A ring is in a band when *k* × pixel size is at
   least the band's start and less than its end. A band's value is the mean
   of the averages of its rings.

Theil–Sen slope
   The median of the slopes between every pair of points. Unlike a
   least-squares line, it is hardly moved by a few wild points.

Decay with distance
-------------------

The two measures of the group *Decay with distance* follow a pulse's
response map from its peak on:

1. **Bins.** The frames from the start of the response map on are cut into
   bins as long as the response map (5 frames, 24 ms, by default), one after
   the other. The first bin is the response map itself. Bins are made up to
   the next stimulus of the protocol, the end of the recording, or *Follow
   the decay for at most* (1500 ms by default) after the peak, whichever
   comes first. The time of a bin is its middle, counted from the frame of
   the maximum of the ROI trace.
2. **Ring averages and bands.** Every bin is made into a map like the
   response map (relative to the pulse's baseline window, blurred), and its
   ring averages and near- and far-band values are taken.
3. **Half-decay times.** For the near band, the far band and every ring out
   to the end of the far band, the time at which its value first falls to
   half of its value in the first bin, interpolated linearly between bins.

The footprint width is measured at the peak only. Whether the footprint
narrows as it fades is shown by the decay with distance: it narrows when the
far band decays faster than the near band (far-near decay ratio below 1).

Baselines, peaks and responses
------------------------------

Measured on the trace (see :doc:`measures` for the trace and the
unstimulated partner). The examples use round numbers.

.. include:: ../_generated/reference_basic.rst

Kinetic measures
----------------

Measured on the pulse's smoothed response over its stretch (see *Words used
below*). The examples all use one made-up response: frames 5 ms apart, no
smoothing, a baseline whose noise has an SD of 0.5 %, and a response that
rises in a straight line from 0 at the stimulus to 50 % 10 frames later,
then falls in a straight line back to 0 over 20 frames.

.. include:: ../_generated/reference_kinetic.rst

Spatial measures
----------------

Measured on the pulse's response map and its rings (see *Words used below*
and *Decay with distance* above). The examples use made-up maps and movies
without noise, 16 µm per pixel, centred on the ROI centre, with no
smoothing, unless they say otherwise.

.. include:: ../_generated/reference_spatial.rst

Near-to-far index
-----------------

.. include:: ../_generated/reference_near_to_far.rst

Per slice
---------

Computed from the per-recording values of all recordings of a slice (one
recording folder).

.. include:: ../_generated/reference_slice.rst
