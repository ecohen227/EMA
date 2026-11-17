Detector settings
=================

Every number of the detector is a setting, with the Standard detector's
value as its default. Times are in ms and distances in µm; the detector
turns them into whole frames (rounded; the event shape's length after the
onset is the number of whole frames within it) and into pixels with the
:term:`time between frames` and the :term:`pixel size`. :doc:`detector`
explains each step.

In the configurator the everyday settings are always shown: the movie, the
rise and decay of the event shape, the pooling width, the event threshold,
the controls, and the distances of the place measures. All other settings
are in the closed *Advanced* section.

Movie
-----

.. include:: ../_generated/spontaneous_settings_movie.rst

Event shape
-----------

The event shape is A·(exp(−t/decay) − exp(−t/rise)) for t > 0 and 0
before, from *Baseline before the onset* to *Length after the onset*. With
*Allow a sloping baseline* its best straight line is removed. It is scaled
so that the sum of its squares is 1.

.. include:: ../_generated/spontaneous_settings_event_shape.rst

Spatial filter
--------------

.. include:: ../_generated/spontaneous_settings_spatial_filter.rst

Detection
---------

.. include:: ../_generated/spontaneous_settings_detection.rst

Controls
--------

.. include:: ../_generated/spontaneous_settings_controls.rst

Measuring
---------

These change what is measured on the events found, not which events are
found.

.. include:: ../_generated/spontaneous_settings_measuring.rst

Tissue
------

All settings of this section are under *Advanced*.

.. include:: ../_generated/spontaneous_settings_tissue.rst

Signal
------

All settings of this section are under *Advanced*.

.. include:: ../_generated/spontaneous_settings_signal.rst

Echoes
------

All settings of this section are under *Advanced*.

.. include:: ../_generated/spontaneous_settings_echoes.rst

Numbers that are not settings
-----------------------------

A few numbers of the measuring are fixed. :doc:`measure_reference` (*Two
sources*) shows where each is used.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - What
     - Value
   * - Pooled trace: its length
     - from 60 frames before the onset to 200 after
   * - Pooled trace: its baseline
     - its median up to 10 frames before the onset
   * - Pooled trace: where its peak is looked for
     - from 10 frames before the onset to 80 after
   * - Decay tau: the frames fitted
     - the 80 frames from the peak
   * - Peak map: the brightness it is measured from
     - the mean from 45 frames before the onset up to 15 before
   * - Peak map: where its peak is looked for
     - the first 35 of the frames from 5 before the onset to 40 after
   * - Peak map: the frames averaged
     - 8: from 3 before its peak to 4 after
   * - Peak map: blur
     - a Gaussian of 1 pixel
   * - Peak map: the disc that finds its peak
     - 48 µm around the event's strongest pixel
   * - Peak map: the far field whose median is subtracted
     - beyond 480 µm (when it has more than 100 tissue pixels)
   * - Gaussian fit: fewest tissue pixels within the fit radius
     - 200
   * - Gaussian fit: limits
     - peak 0 to 100 %, width 8 to 400 µm, offset −5 to 5 %, centre at most
       128 µm from the event's strongest pixel
   * - Echoes: weakest region that counts or removes another
     - 5 × noise (the event threshold, if that is lower)
