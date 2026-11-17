Spontaneous Event Configurator
==============================

The configurator makes :term:`detectors <detector>`. A detector tells the
Spontaneous Event Analysis how to find spontaneous dopamine
:term:`events <event>` in
:term:`unstimulated recordings <unstimulated recording>` (``no1.tif``,
``no2.tif`` …), and what to measure on them: per event, per recording and
per slice. Detectors are kept in a
:term:`library` inside EMA, like the evoked protocols, so the analysis can
use them by name.

A detector is tried live on an example recording: the events it finds are
circled on the slice, and each one's peak map, pooled trace and measures
are shown.

.. figure:: ../screenshots/spontaneous_configurator.png
   :width: 100%

   The configurator with the built-in *Standard detector*, on the sample
   unstimulated recording with two events added to it (see
   :doc:`detector`). Left: the detector, in three tabs. Right: each pixel's
   largest strength with the events circled, the selected event's peak map
   and pooled trace, and its measures.

One detector is built in, the :term:`Standard detector`. It finds events at
least 8 times the :term:`noise` after a 128 µm :term:`spatial filter` and a
filter shaped like a dLight event (the :term:`event shape`). Every number it
uses is a setting (see :doc:`settings`), and :doc:`detector` explains each
step.

The Standard detector is read-only. Change it and press *Save*: EMA asks
for a new name and keeps your version as a detector of your own.

.. toctree::
   :maxdepth: 2

   walkthrough
   detector
   settings
   measure_reference
   choosing_measures
   detector_file
