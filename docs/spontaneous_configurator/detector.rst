How the detector works
======================

What it looks for
-----------------

A typical spontaneous event peaks at about 3 % :term:`dF/F`, is about
150 µm wide, rises in about 30 ms and falls to half in about 100 ms. One
pixel's :term:`noise` is 4–6 % dF/F per frame, larger than the event. The
detector therefore compares each pixel's trace with the expected
:term:`event shape` and pools neighbouring pixels before it looks for
events.

.. figure:: ../figures/spontaneous_steps.png
   :width: 100%

   The Standard detector on the sample unstimulated recording (``no6.tif``
   of the 2P sample folder), with two events added to it: a peak of 4 %,
   150 µm wide, and a peak of 3 %, 120 µm wide, both with the time course of
   a dLight event; the rest is the real recording. **1** The event shape,
   before and after its best straight line is removed. **2** One pixel's
   dF/F at the first event, and the same pooled by the 128 µm spatial
   filter. **3** The :term:`strength` at the event's pixel: the event
   reaches 23 × noise; the dips just before and after it are
   :term:`echoes <echo>`. **4** Each pixel's largest strength over the
   recording, with both events found.

The steps
---------

Every number below is a setting (in *italics*; see :doc:`settings`), given
with its value in the :term:`Standard detector`.

0. **The recording.** The first 20 frames (after the one EMA always drops)
   and the last 10 are left out (*Leave out the first*, *Leave out the
   last*).
1. **Tissue.** Each pixel's resting brightness :term:`F0` is its mean over
   frames 10 to 94. The image is cut into blocks of 4 × 4 pixels (64 µm).
   A block is searched as :term:`tissue` unless its F0 is below 0.3 × the
   median block's, or at least half of it lies under the electrode. The
   electrode comes from the ROI file, or else is found automatically from
   the folder's stimulated recordings.
2. **dF/F and spikes.** Each pixel's brightness is divided by a smooth curve
   fitted to it over time (a polynomial of order 4), which removes
   :term:`bleaching`: dF/F = F ÷ curve − 1. A running median over 3 frames
   removes single-frame camera spikes.
3. **Event shape.** The expected event is exp(−t/200 ms) − exp(−t/12 ms),
   from 100 ms before its onset (21 frames) to 600 ms after it (123
   frames). With *Allow a sloping baseline*, its best straight line is
   removed (figure, panel 1), so that a slow drift under an event does not
   change its strength. At every frame, each pixel's trace is compared with
   this shape: the result rises where an event starts.
4. **Spatial filter.** Each frame of the result is blurred with a
   :term:`Gaussian` whose σ is the *Pooling width*, 128 µm, about the width
   of a typical event. Only the tissue is pooled, so the image edges and
   the electrode do not pull the values down.
5. **Field-wide signal.** Each frame's median over the tissue is
   subtracted (*Remove the field-wide signal*). This removes changes shared
   by the whole field.
6. **Strength.** For each pixel, the filtered signal is expressed in ×
   noise: (value − its median) ÷ its noise level. The noise level is
   1.4826 × the median absolute deviation, taken over every second frame.
   For random noise this equals the standard deviation, and events barely
   change it.
7. **Regions.** Neighbouring pixels and frames (touching by a side, an
   edge or a corner) with a strength of at least 3 × noise (*Region
   threshold*) form a :term:`region`. A region whose largest strength
   reaches 8 × noise (*Event threshold*) is an event. It is placed at its
   strongest pixel and frame, which give its position and its onset.
8. **Echoes.** The filters also turn each event into a dip of the opposite
   sign just before and just after it. So of two regions of opposite sign
   whose onsets are at most 533 ms apart and whose strongest pixels are at
   most 256 µm apart, only the stronger counts (*Drop echoes*). The rule
   applies to dips too, which keeps the sign-flipped control fair. Regions
   weaker than 5 × noise neither count nor remove another region.
9. **The end.** Onsets in the last 320 ms of the searched part are not
   counted (*Leave out onsets in the last*): there the event shape reaches
   the last frames, where the bleaching correction is least certain.

The :term:`searched time` is what remains for onsets: the frames left after
step 0, minus the length of the event shape plus one, minus the 320 ms of
step 9. For a TIFF of 1,650 frames that is 1,410 frames, 6.84 s.

The controls
------------

Two controls run with every search; both are counted per recording.

**Sign-flipped.** The strength movie is turned upside down and searched
for dimming events, with the same rules. Noise gives dimming events as
often as brightening ones; dopamine release does not. The
:term:`sign-flipped` count therefore estimates how many of the events are
false alarms. It slightly overestimates them, because real dimming and
artefacts (bubbles, debris) count too.

**Time-reversed.** The dF/F movie is played backwards and searched again
from step 3. A real event, with its fast rise and slow decay, looks wrong
backwards and is mostly not found; noise is found as often either way. A
strong event can still be found backwards. This second search makes each
recording take longer; switch *Count time-reversed events* off to save the
time.

What the detector measures
--------------------------

The spatial filter finds events; it does not measure them. Each event is
measured afterwards on the dF/F movie of step 2:

* its **width and fitted peak** from a Gaussian fitted to its
  :term:`peak map`;
* its **time course** (rise, half-decay and more) from its
  :term:`pooled trace`, whose peak is lowered by the pooling. Use the
  fitted peak for amplitude.

:doc:`measure_reference` gives every measure in full.

Changing the pooling width and the event threshold
--------------------------------------------------

A larger *Pooling width* finds wide, faint events better; a smaller one
finds narrow events. A lower *Event threshold* finds more events, and more
false ones: compare the sign-flipped count.
