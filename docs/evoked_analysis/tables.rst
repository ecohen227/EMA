The two Excel files
===================

Every run writes two files into the output folder:

``Evoked per recording.xlsx``
   One row per recording: every per-recording measure of the protocol.

``Evoked per slice.xlsx``
   One row per slice (recording folder): every per-slice measure of the
   protocol, such as the mean of the PPR over the slice's recordings.

Both have the same sheets:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Sheet
     - What it holds
   * - **Recordings** / **Slices**
     - The whole table: the folder (and, per recording, the file and its
       unstimulated partner), the labels, the condition (such as
       *Current (µA)*), whether the ROI was reviewed in ROI Selection, then
       one column per measure, with its unit in the heading. Use it for
       Excel, R or Python, or for a Prism *Multiple variables* table.
   * - one sheet per measure
     - The same numbers laid out to paste into Prism (below). The sheet is
       named after the measure; ``/`` becomes ``÷`` (``P2÷P1``), because
       Excel does not allow it.
   * - **Notes**
     - Every recording that was not measured and why, every value that
       could not be measured (such as a fit that did not converge), and the
       labels to check.
   * - **About**
     - When and with which protocol the file was made, the ROI file, the
       labels and their spellings, and the definition and unit of every
       measure.

A value that could not be measured is an **empty cell**, never 0. Rows are
in the order of the groups (see below), then of the labels.

Groups
------

The slices are grouped by the values of the labels ticked under **Groups in
the tables**. With *Genotype* and *Treatment* ticked, the groups are
WT CTRL, WT IFN, HET CTRL and HET IFN, in the order the values are listed on
the Labels tab. A slice whose label was not found goes into a group such as
*(no Genotype) CTRL*. With no label ticked, all slices are one group.

Per recording: a Prism grouped table
------------------------------------

Each measure sheet of ``Evoked per recording.xlsx`` is a grouped table: one
row per condition (each current, or each recovery delay), one group of
columns per group of slices, and in each group one column per slice. A
slice keeps its column in every row, so the rows of one column are the
repeated measures of one slice. For example, *P1 response* of made-up
recordings:

.. list-table::
   :header-rows: 0

   * - **P1 response (%)**
     -
     -
     -
     -
   * - *Prism: grouped table, 2 replicate values …*
     -
     -
     -
     -
   * -
     - **WT CTRL**
     -
     - **HET CTRL**
     -
   * - **Current (µA)**
     - Animal 5820 Slice 1
     - Animal 5770 Slice 2
     - Animal 5819 Slice 1
     -
   * - 100
     - 3.40
     - 4.17
     - 2.31
     -
   * - 200
     - 6.80
     - 8.17
     - 4.73
     -
   * - 300
     - 9.11
     - 11.04
     - 6.32
     -

Every group has as many columns as the largest group; the columns a smaller
group does not need stay empty. Row 4 names each slice by its number
labels (here Animal and Slice), or by its folder when it has none.

To paste it into Prism:

1. Make a **Grouped** table, with *Enter N replicate values in side-by-side
   subcolumns*, N being the number in row 2 of the sheet (here 2). For a
   curve against the current, an **XY** table with N replicate Y values
   works the same way.
2. In Excel, select from the first condition in column A (row 5) down to the
   last value on the right, and copy.
3. In Prism, click the first row title (in an XY table, the first X) and
   paste. The group titles are in row 3 of the sheet; type them as the data
   set titles.

When a slice has two recordings with the same condition (such as
``300uA.tif`` and ``300uA 2.tif``), the measure sheets show the first by
name, and the *Notes* sheet says so. Both are on the *Recordings* sheet.

Per slice: a Prism column or grouped table
------------------------------------------

Each measure sheet of ``Evoked per slice.xlsx`` is, by default, a
**column table**: one column per group, one value per slice:

.. list-table::
   :header-rows: 0

   * - **P1 response mean 100-400 (%)**
     -
     -
     -
   * - *Prism: column table, one column per group …*
     -
     -
     -
   * - **WT CTRL**
     - **WT IFN**
     - **HET CTRL**
     - **HET IFN**
   * - 6.44
     - 7.13
     - 4.45
     - 5.16
   * - 7.79
     -
     -
     - 5.79

Make a **Column** table in Prism, select the values from row 4 down, and
paste them into the first value of the first column.

For a two-way comparison, such as genotype × treatment, choose a label under
**Rows of the per-slice measure sheets**, for example *Treatment*, and tick
only *Genotype* as group. Each sheet is then a **grouped table**: one row per
treatment (CTRL, IFN), one group of columns per genotype, each slice a value
in its row. Paste it into a Prism grouped table with side-by-side
subcolumns, as above.

If the protocol has no per-slice measures, the per-slice file only lists
the slices. Choose them in the configurator, under *Comparisons and
summary*.
