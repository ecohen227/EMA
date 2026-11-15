Measure reference
=================

Every number a detector can report, one by one: how it is named, its unit,
its definition, its formula, how it is computed, when it is left empty,
what it reflects and what to be careful of. *Italic* names are settings
(see :doc:`settings`). An empty value means "could not be measured"; it is
never replaced by 0, and summaries leave it out.

.. figure:: ../figures/spontaneous_event.png
   :width: 100%

   How an event is measured: the first planted event of
   :doc:`detector`'s figure (4 % peak, σ 150 µm). Left: its peak map with
   the fitted Gaussian's half-maximum circle and the fit radius. Right: its
   pooled trace, with the detected onset, the peak and the half-decay.

Two sources
-----------

**The peak map** gives the event's size and centre. A Gaussian
peak·exp(−r²/2σ²) + offset is fitted to the dF/F map at the event's peak,
over the tissue within *Fit the width within*. The fit is **good** when its
fit quality reaches *Smallest fit quality*, its σ is below *Largest width*
and its peak is above 0; otherwise width, fitted peak and size are empty
and the event's position is its z maximum.

**The pooled trace** gives the event's time course: the dF/F movie through
the detector's spatial filter, at the event's maximum. The pooling makes it
clean enough to time, but dilutes its peak, so its *local peak* is lower
than the *fitted peak*.

Per event
---------

.. include:: ../_generated/spontaneous_reference_event.rst

Per recording
-------------

.. include:: ../_generated/spontaneous_reference_recording.rst

Per slice
---------

A slice is one recording folder: its measures pool all its searched
recordings.

.. include:: ../_generated/spontaneous_reference_slice.rst

.. include:: ../_generated/spontaneous_reference_summary.rst
