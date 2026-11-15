The detector's settings
=======================

Every number of the detector is a setting, with detector v5's value as its
default. Times are in ms and distances in µm; the detector converts them to
whole frames (rounded; the template's length after the onset is the number
of whole frames within it) and to pixels with the frame interval and the
pixel size. :doc:`detector` explains each step.

Movie
-----

.. include:: ../_generated/spontaneous_settings_movie.rst

Tissue
------

.. include:: ../_generated/spontaneous_settings_tissue.rst

Signal
------

.. include:: ../_generated/spontaneous_settings_signal.rst

Template
--------

The template is A·(exp(−t/decay) − exp(−t/rise)) for t > 0 and 0 before,
from *Baseline before the onset* to *Length after the onset*, minus its best
straight line (with *Fit a sloping baseline*), scaled to unit length.

.. include:: ../_generated/spontaneous_settings_template.rst

Spatial filter
--------------

.. include:: ../_generated/spontaneous_settings_spatial_filter.rst

Detection
---------

.. include:: ../_generated/spontaneous_settings_detection.rst

Echoes
------

.. include:: ../_generated/spontaneous_settings_echoes.rst

Controls
--------

.. include:: ../_generated/spontaneous_settings_controls.rst

Measuring
---------

These change what is measured on the events found, not which events are
found.

.. include:: ../_generated/spontaneous_settings_measuring.rst

Fixed in the code
-----------------

A few numbers of the measuring are not settings. They follow the study and
are listed here so nothing is hidden:

* the event trace runs from 60 frames before the onset to 200 after; its
  baseline is its median up to 10 frames before the onset, and its peak is
  looked for from 10 frames before the onset to 80 after;
* the peak map is measured from the mean of frames 45 to 15 before the
  onset, blurred by 1 pixel, and averaged over 8 frames around its peak,
  found in the first 35 of the frames from 5 before the onset to 40 after;
* the far field whose median is subtracted from the peak map starts at
  480 µm; the fitted Gaussian's centre may move at most 128 µm, and its σ
  lies between 8 and 400 µm;
* the decay time constant is fitted over the 80 frames from the peak.
