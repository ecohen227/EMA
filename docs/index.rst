EMA
===

EMA analyses movies of electrically stimulated brain slices (dLight and
similar sensors, recorded as TIFF stacks). It is a set of five packages
behind one start window. Each package does one job and hands its result to
the next one as a file.

.. list-table::
   :header-rows: 1
   :widths: 30 55 15

   * - Package
     - What it does
     - Status
   * - :doc:`ROI Selection <roi_selection/index>`
     - Finds the ROI and the electrode of every recording folder, lets you
       correct them and flag bad recordings.
     - Ready
   * - :doc:`Evoked Analysis Configurator <evoked_configurator/index>`
     - Makes the protocols the evoked analysis measures with: the pulses,
       their windows, and what is derived from them.
     - Ready
   * - :doc:`Evoked Analysis <evoked_analysis/index>`
     - Measures the evoked responses inside the selected ROIs with a
       protocol, and writes the results, labelled from the folder names, in
       two Excel files laid out for Prism.
     - Ready
   * - :doc:`Spontaneous Event Configurator <spontaneous_configurator/index>`
     - Makes the detectors the spontaneous-event analysis uses: how events
       are found and what is measured on them.
     - Ready
   * - :doc:`Spontaneous Event Analysis <spontaneous_analysis/index>`
     - Searches the unstimulated recordings of every folder under a
       recordings folder with a detector, and writes the events and slices, labelled from the
       folder names, in two Excel files laid out for Prism.
     - Ready

.. toctree::
   :maxdepth: 2
   :caption: Using EMA

   getting_started
   roi_selection/index
   evoked_configurator/index
   evoked_analysis/index
   spontaneous_configurator/index
   spontaneous_analysis/index

.. toctree::
   :maxdepth: 1
   :caption: For developers

   development
   reference
