EMA
===

EMA analyses movies of electrically stimulated brain slices (dLight and
similar sensors, recorded as TIFF stacks). It is a set of four packages
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
   * - Evoked Analysis
     - Measures the evoked responses inside the selected ROIs.
     - Planned
   * - Evoked Analysis Configurator
     - Sets the windows, fits and comparisons of the evoked analysis.
     - Planned
   * - Spontaneous Event Analysis
     - Finds and measures spontaneous events in unstimulated recordings.
     - Planned

.. toctree::
   :maxdepth: 2
   :caption: Using EMA

   getting_started
   roi_selection/index

.. toctree::
   :maxdepth: 1
   :caption: For developers

   development
   reference
