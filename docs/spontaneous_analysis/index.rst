Spontaneous Event Analysis
==========================

The spontaneous-event analysis searches the unstimulated recordings
(``no1.tif``, ``no2.tif`` …) of every folder under a recordings folder with a
detector, and writes two Excel files laid out for Prism: one row per event in the
first, one row per slice in the second. Each row carries the labels read
from its folder names, such as the genotype and the treatment.

It needs

* a **recordings folder**: every folder in it that holds unstimulated
  recordings is searched;
* a **detector** made in the :doc:`Spontaneous Event Configurator
  <../spontaneous_configurator/index>`, or the built-in *Detector v5*;
* an **output folder**, outside the recordings;
* optionally, the **ROI file** (``roi_selections.json``) that
  :doc:`ROI Selection <../roi_selection/index>` made for the same recordings
  folder, for its reviewed electrodes, release centres and flags.

.. figure:: ../screenshots/spontaneous_analysis.png
   :width: 100%

   The Spontaneous Event Analysis after a run on four made-up slices (the
   sample's unstimulated recording with events planted in it). It is the
   window of the :doc:`Evoked Analysis <../evoked_analysis/index>`, with a
   recordings folder (the ROI file optional) and a detector in place of a
   protocol.

Step by step
------------

The window works like the Evoked Analysis's (see
:doc:`../evoked_analysis/index`):

1. **Recordings folder**. The line under it says how many of its folders
   hold unstimulated recordings. **ROI file**, optionally: the line under it
   says how many of those folders it covers.
   Then the **Folders** to search, for example *Only folders with*
   ``input output``. Unstimulated recordings in the 11P folders can be
   searched too: run them as a separate analysis, or together, with a label
   that tells them apart.
2. **Detector**: one from the library, or **Open…** for a detector file kept
   elsewhere. The line under it says how many measures it reports, its
   threshold and its filter width.
3. **Output folder**: the line under it says what a run will do.
4. **Labels**: the same labels, spellings and near misses as the evoked
   analysis (see :doc:`../evoked_analysis/labels`); both analyses start with
   the labels last used in either.
5. **Group by** and **Slice sheets**: the groups of the Prism sheets.
6. **Run the analysis**. **Stop** stops after the recordings being searched;
   the folders finished so far are kept.

What is searched in each folder
-------------------------------

Each recording folder is one **slice**. Its unstimulated recordings, named
``no`` and a number, are searched, without those with one of the detector's
skip words (``red``) and those flagged in the ROI file. Each is searched as
:doc:`../spontaneous_configurator/detector` describes, and every measure is
measured on every event (:doc:`../spontaneous_configurator/measure_reference`).
The per-slice measures pool all searched recordings of the folder.

The detector leaves the electrode out of the searched tissue, and the place
measures need the release centre (the centre of evoked release). Each
folder's come from:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - *Electrode and centre*
     - Where they came from
   * - ``ROI file, reviewed`` / ``ROI file``
     - Its entry in the ROI file, reviewed in ROI Selection or not.
   * - ``automatic``
     - Found from the folder's stimulated recordings, as ROI Selection's
       automatic detection does, when the ROI file does not cover the folder
       (or there is no ROI file).
   * - ``none``
     - The folder has no stimulated recording: it is searched without an
       electrode, and its place measures (distances, electrode side, share
       near the release centre) are empty.

The *Electrode and centre* column of the tables says which, and the *Notes*
sheet points out the automatic and the missing ones. An ROI file made for
another recordings folder is not used.

Searching takes time: about 9 s per recording on one processor core.
Several recordings are searched at once, one per core but one (at most 8),
each in a process of its own: on a 12-core laptop, about 3 s per recording,
or 4 hours for 4,500 recordings. Switching off the time-reversed control in
the detector saves about 40 %.

Running again
-------------

As in the evoked analysis, everything is kept in the output folder, in
``spontaneous_analysis.json``: the detector, the labels, the groups, and
every recording's and every event's measures. A new run with the same
output folder searches only what it has to:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Since the last run
     - What happens
   * - Nothing changed
     - Nothing is searched; the files are written again (in seconds).
   * - New folders in the ROI file
     - Only the new folders are searched, and added to the files.
   * - A folder's entry in the ROI file changed (or the ROI file now covers
       it), or a recording was added, replaced or removed
     - That folder is searched again.
   * - A folder is no longer under the recordings folder (or in the folder
       filter)
     - EMA asks whether to keep its results.
   * - The labels, the groups, or which measures the detector reports
     - Nothing is searched: every measure is kept, so the files are only
       written again. Press **Rewrite the tables**, or run.
   * - The detector's settings or skip words, or EMA was updated
     - Every folder is searched again, and both files are replaced. EMA
       asks first.

Checked on real recordings
--------------------------

On the 25 paired-pulse folders of the animals F5819, F5772, M5820 and M5771,
with an ROI file of ROI Selection's automatic detection, the analysis
found the same number of events as the metric study's detector v5 in every
one of the 62 recordings the study had searched (55 events). Over all 151
unstimulated recordings it found 137 events in 17.2 minutes (8.0 per
minute), with 2 sign-flipped and 1 time-reversed detections.

.. toctree::
   :maxdepth: 2

   tables
