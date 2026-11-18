The evoked Excel files
======================

Every run writes two files into the output folder:

* ``Evoked per recording.xlsx``: one row per recording;
* ``Evoked per slice.xlsx``: one row per slice (recording folder), unless
  the protocol has *Write Evoked per slice.xlsx* unticked (tab
  *Comparisons and summary* of the Evoked Analysis Configurator).

**Example files**, made from eight made-up slices with the built-in
*2P paired pulse* protocol, grouped by genotype and treatment:
:download:`Example - Evoked per recording.xlsx <../examples/Example - Evoked per recording.xlsx>`
and :download:`Example - Evoked per slice.xlsx <../examples/Example - Evoked per slice.xlsx>`.
The tables below are taken from them.

What is in each file
--------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Sheet
     - What it holds
   * - **Recordings**
     - Everything in one table: the folder, the recording and its partner,
       the labels, the condition, *ROI reviewed* (yes when the folder was
       reviewed in ROI Selection), then one column per measure, with its
       unit. Use it in Excel, R or Python, or in a Prism *Multiple
       variables* table.
   * - **Slices** (per-slice file)
     - The same for slices: the folder, the labels, *Recordings measured*,
       *ROI reviewed*, then one column per per-slice measure.
   * - one sheet per measure
     - The same numbers laid out to paste into Prism (below). ``/`` in a
       name becomes ``÷`` (``P2÷P1``).
   * - **Notes**
     - What was not measured and why, labels to check, and why a slice was
       left out.
   * - **Exclusions** (when the protocol has exclusions)
     - Each exclusion in words, then one row per slice and exclusion: its
       group, its value, the lowest and highest value kept, and whether it
       is left out (*yes*, *no*, or *not tested* when its value or the limits
       could not be worked out). A slice left out by any exclusion is in
       neither file.
   * - **About**
     - The protocol, the labels, the exclusions, and what every measure is.

A value that could not be measured is an **empty cell**, never 0. Each
pulse's peak (``P1 peak``) is written only when the protocol says so
(*Write the peak of each pulse too*, on the *Pulses and windows* tab); its
response always is.

The start of the *Recordings* sheet of the example (some of its columns):

.. include:: ../_generated/example_recordings.rst

Per recording: Prism grouped tables
-----------------------------------

Each measure sheet of ``Evoked per recording.xlsx`` is a
:term:`grouped table`: one row per :term:`condition` (each current), a
group of columns per group of slices (here WT CTRL, WT IFN, HET CTRL and
HET IFN), and one column per slice. Rows 1 and 2 give the measure with its unit and how to
paste it; the *P1 response* sheet of the example from row 3 on:

.. include:: ../_generated/example_prism_recording.rst

To paste it into Prism:

1. Make a **Grouped** table with *N replicate values in side-by-side
   subcolumns*; N is given in row 2 (here 2). For a curve against the
   current, an **XY** table with N replicates works the same way.
2. Copy from cell A5 to the last value.
3. Click the first row title in Prism (in an XY table, the first X) and
   paste. Type the group titles (row 3) as the data set titles.

Smaller groups are padded with empty columns, so every group is as wide as
the largest. A slice keeps its column in every row.

The rows are the conditions only: a recording whose name does not start
with a number is on the *Recordings* sheet only. (When no recording has a
condition, the rows are the file names instead.) When a slice has two
recordings with the same condition, such as ``50uA.tif`` and
``50uA (2).tif``, the sheet shows the plainest name, ``50uA.tif``; to use
the other one, flag ``50uA.tif`` in ROI Selection. The *Notes* sheet lists
both cases.

Per slice: Prism column tables
------------------------------

Each measure sheet of ``Evoked per slice.xlsx`` is a :term:`column table`:
one column per group and one value per slice. The *P1 response mean 100-400* sheet of the
example from row 3 on:

.. include:: ../_generated/example_prism_slice.rst

Make a **Column** table in Prism, copy from cell A4 to the last value, and
paste at the first value.

For a two-way comparison (genotype × treatment), set **Slice sheets** to
*One row per Treatment* and group by *Genotype* only. Each sheet is then a
grouped table with one row per treatment; paste it as above.

If the protocol has no per-slice measures, the per-slice file only lists
the slices. Choose them in the configurator, under *Comparisons and
summary*.
