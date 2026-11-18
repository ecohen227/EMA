What EMA expects from your recordings
=====================================

Recordings and folders
----------------------

A :term:`recording` is one TIFF movie (``.tif`` or ``.tiff``): one trial.
TIFF files smaller than 1 MB, such as reference snapshots, are not
recordings and are ignored.

A :term:`recording folder` is any folder that holds at least one recording.
Each recording folder is one :term:`slice` in the tables. The
:term:`recordings folder` is the top folder you choose in EMA; it can hold
one slice, one animal or a whole study. For example:

.. code-block:: text

   Recordings/                          the recordings folder you choose
   └── Females/
       └── LKI HET F5819/
           └── IFNy 4HR/
               └── Slice 2/
                   ├── input output/        a recording folder
                   │   ├── 50uA.tif
                   │   ├── 100uA.tif
                   │   ├── …
                   │   ├── 300uA.tif
                   │   ├── no1.tif
                   │   ├── …
                   │   └── no6.tif
                   └── 11p at 200uA/        another recording folder
                       ├── hi1.tif … hi4.tif
                       └── no1.tif … no5.tif

The names of the folders above a recording folder carry its
:term:`labels <label>`: line, genotype, treatment, treatment time, sex,
animal and slice (see :doc:`evoked_analysis/labels`). Here they are LKI, HET, IFN, 4H,
F, 5819 and 2.

File names
----------

Stimulated recordings
   Named after their current, such as ``200uA.tif``. The number the name
   starts with is the recording's :term:`condition` (200). The recordings of
   a pulse train are named ``hi1.tif`` … ``hi4.tif``; the protocol lists
   them with their conditions.

Unstimulated recordings
   An :term:`unstimulated recording` is made the same way as a stimulated
   one (same light, same number of frames) but without the electrical
   stimulus. Its name is ``no`` followed by a number: ``no1.tif``,
   ``no 2.tif`` and ``no1 red.tif`` are all unstimulated; upper and lower
   case do not matter. EMA uses them in two ways:

   * the Evoked Analysis corrects each stimulated recording for
     :term:`bleaching` with an unstimulated one, its
     :term:`unstimulated partner`;
   * the Spontaneous Event Analysis searches them for spontaneous events.

Skip words
   A file whose name holds one of the :term:`skip words` is left out, such
   as ``200uA red.tif`` or ``test stim 200uA.tif``. Only whole words count:
   the parts of the name between spaces, ``_`` and ``-``, so ``red`` leaves
   out ``no1_red.tif`` but not ``reduced.tif``. Skip words are set in three
   places:

   .. list-table::
      :header-rows: 1
      :widths: 40 25 35

      * - Where
        - Default
        - Leaves the recording out of
      * - ROI Selection, *Skip recordings with these words*
        - ``red``
        - the automatic ROI and electrode only
      * - Each protocol, *Skip recordings with these words*
        - ``red``, ``test`` (none in the built-in 11P protocol)
        - the Evoked Analysis
      * - Each detector, *Skip recordings with these words*
        - ``red``
        - the Spontaneous Event Analysis

Time stamps
   The camera software writes the date and time of each recording into
   the TIFF. By default the Evoked Analysis uses them to find the
   unstimulated recording made right after a stimulated one.

Frames, time and distance
-------------------------

EMA drops the first frame of every TIFF. So *frame 0* in EMA is the second
frame of the file. All frame numbers in the settings and in the plots are
counted this way.

A :term:`window` is a range of frames given *from* one frame *up to*
another; the second frame itself is not included.

The defaults are set for the lab's recordings:

* 128 × 128 pixels, with the stimulus near frame 103;
* a :term:`time between frames` of 4.849 ms;
* a :term:`pixel size` of 16 µm (4× objective).

The time between frames and the pixel size are settings of each protocol
and each detector, so other recordings can be measured too.

Your recordings are only read
-----------------------------

EMA never changes, moves or renames a recording, and it never writes into
the recordings folder. ROI Selection and both analyses write their files
into an :term:`output folder`, and refuse one that lies inside the
recordings folder. The configurators only read the example folder you try
them on.
