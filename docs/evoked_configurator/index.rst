Evoked Analysis Configurator
============================

The configurator makes **protocols**. A protocol tells the evoked analysis
what to measure in a recording of an evoked response: which trace, which
recordings, the baseline and peak window of every pulse, and what is
derived from them: comparisons, exponential fits, kinetic measures of each
pulse's time course, spatial measures of how its response spreads over the
slice and how that spread changes as it decays, and curves fitted across
the recordings of a slice. Protocols are saved in a library inside EMA, so the analysis can
use them by name.

Every protocol is built from one template, a train of pulses with an
optional recovery pulse; the built-in protocols are two fillings of it.

.. figure:: ../screenshots/configurator.png
   :width: 100%

   The configurator with the built-in 2P protocol. Left: the protocol, in
   five tabs. Right: the protocol tried on a real recording, with its
   windows and fit on the trace, and every measure it will produce, with
   its value on that recording.

Three protocols are built in:

.. list-table::
   :widths: 25 75

   * - **2P paired pulse**
     - Two pulses 4 s apart. Each stimulated recording is corrected for
       bleaching with the unstimulated recording made right after it. Measured:
       the baselines B1 and B2, the peaks P1 and P2, the response (dF/F) of
       each pulse, the paired-pulse ratio, and the decay time constant
       after P1. Per slice: the minimum, maximum and mean of each over the
       recordings, the mean over 100 to 400 µA, and how much the baselines
       drifted.
   * - **2P paired pulse, uncorrected**
     - The same, with every recording measured as recorded, without an
       unstimulated partner: for slices recorded without unstimulated
       recordings.
   * - **11P pulse train**
     - Ten pulses at 10 Hz and a recovery pulse 0.5 to 5 s later. Each
       stimulated recording (``hi1`` … ``hi4``) is divided by the
       unstimulated one recorded after it (``no2`` … ``no5``). Measured: the
       baseline BL before the train, P1 … P10, the recovery pulse P11 above
       its own baseline, P2/P1, P10/P1, P11/P1, P11/P10, and every pulse
       relative to P1.

Built-in protocols cannot be changed. To change one, change it and save it
under a new name: it is then a protocol of your own.

.. toctree::
   :maxdepth: 2

   walkthrough
   measures
   measure_reference
   choosing_measures
   protocol_file
