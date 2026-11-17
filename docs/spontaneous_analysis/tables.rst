The spontaneous Excel files
===========================

Every run writes two files into the output folder:

* ``Spontaneous per event.xlsx``: one row per event, and one per recording;
* ``Spontaneous per slice.xlsx``: one row per slice (recording folder).

**Example files**, made from four made-up slices (the sample's unstimulated
recording with events added to it) with the *Standard detector*, grouped by
genotype and treatment:
:download:`Example - Spontaneous per event.xlsx <../examples/Example - Spontaneous per event.xlsx>`
and :download:`Example - Spontaneous per slice.xlsx <../examples/Example - Spontaneous per slice.xlsx>`.
The tables below are taken from them.

What is in each file
--------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Sheet
     - What it holds
   * - **Events**
     - One row per event: its folder and recording, the labels, its number
       in the recording (by onset), and the detector's chosen per-event
       measures, with their units.
   * - **Recordings**
     - One row per searched recording: its folder, the labels, *Electrode
       and centre* (where the folder's electrode and ROI centre came from,
       see :doc:`index`), and the chosen per-recording measures: events,
       searched time, rate, controls.
   * - **Slices**
     - One row per slice: its folder, the labels, *Recordings searched*,
       *Electrode and centre*, and the chosen per-slice measures, including
       the summaries of event measures (such as *width median*).
   * - one sheet per measure
     - The same numbers laid out to paste into Prism (below).
   * - **Notes**
     - What was not searched and why, and labels to check.
   * - **About**
     - The detector and its main settings, the labels, and what every
       measure is.

Only the measures the detector reports are in the files; change them in the
configurator. A value that could not be measured is an **empty cell**,
never 0. A slice with no event has a rate of 0 and empty event summaries.

The start of the *Events* sheet of the example (some of its columns):

.. include:: ../_generated/example_spontaneous_events.rst

Per event: Prism column tables
------------------------------

Each measure sheet of ``Spontaneous per event.xlsx`` is a
:term:`column table`: one column per group, with every event of the group's
slices below it: the distribution of
the measure, for a scatter plot, a box plot or a cumulative distribution.
The *width* sheet of the example, from row 3 on:

.. include:: ../_generated/example_spontaneous_width.rst

Make a **Column** table in Prism, copy from cell A4 to the last value, and
paste at the first value. Events are not independent (they come from a few
slices and animals), so compare groups on the per-slice file, and use this
one to show the distributions.

Per slice: Prism column or grouped tables
-----------------------------------------

Each measure sheet of ``Spontaneous per slice.xlsx`` has one column per
group and one value per slice. The *Slices* sheet and the *rate* sheet of
the example:

.. include:: ../_generated/example_spontaneous_slices.rst

.. include:: ../_generated/example_spontaneous_rate.rst

Make a **Column** table in Prism and paste from cell A4. For a two-way
comparison (genotype × treatment), set **Slice sheets** to *One row per
Treatment* and group by *Genotype* only: each sheet is then a
:term:`grouped table` with one row per treatment. Paste it from cell A5 into a Prism grouped
table with side-by-side subcolumns.
