Working on EMA
==============

The code is meant to be read by the people who use it. It favours plain
functions, full words for names, and short files with one job each.

Layout
------

.. code-block:: text

   EMA_V3/
   ├── EMA.pyw                  double-click to start
   ├── ema/
   │   ├── app.py               starts Qt, shows errors in a dialog, opens the launcher
   │   ├── launcher.py          the start window with the four packages
   │   ├── recordings.py        finding and reading TIFF movies (read-only)
   │   ├── labels.py            labels read from folder names, and near misses
   │   ├── user_settings.py     remembers the last folders used
   │   ├── blit.py              fast redrawing of things that follow the mouse
   │   ├── evoked/              protocols and measuring (numpy only, no GUI)
   │   │   ├── protocol.py      what a protocol holds, its checks and its file
   │   │   ├── measures.py      measuring one trace with a protocol; fits; slice summaries
   │   │   ├── metrics.py       the catalogue of kinetic and spatial measures, and the spatial settings
   │   │   ├── kinetics.py      kinetic measures of one pulse
   │   │   ├── spatial.py       response maps, rings and the spatial measures
   │   │   ├── traces.py        the measured trace and movie, with the unstimulated partner
   │   │   ├── analysis.py      running a protocol on the folders of an ROI file; the kept results
   │   │   ├── workbook.py      the two Excel files, laid out for Prism
   │   │   ├── metric_details.py  the full description of every measure, for the measure reference
   │   │   ├── template.py      the template every protocol can be built from
   │   │   ├── library.py       built-in and saved protocols
   │   │   ├── presets.py       the built-in protocols, as code
   │   │   └── presets/         … and as the files EMA ships
   │   ├── evoked_analysis/
   │   │   ├── window.py        the Evoked Analysis window and its worker thread
   │   │   └── labels_editor.py the Labels and Near misses tabs
   │   ├── evoked_configurator/
   │   │   ├── window.py        the configurator window and its library bar
   │   │   ├── editors.py       the Recordings and Pulses tabs
   │   │   ├── measure_editors.py  the Kinetics, Spatial, and Comparisons tabs
   │   │   ├── spatial_plot.py  the response map and ring profile of the Spatial tab
   │   │   ├── template_dialog.py  "New…": the template form
   │   │   ├── plot.py          the example trace with draggable windows
   │   │   ├── example.py       ROI traces of an example folder
   │   │   ├── pulse_dialog.py  "Place pulses…"
   │   │   └── widgets.py       small widgets the tabs are built from
   │   └── roi_selection/
   │       ├── settings.py      every setting: default, label, help text
   │       ├── detection.py     the automatic ROI and electrode (numpy only, no GUI)
   │       ├── selections.py    the ROI file
   │       ├── setup_dialog.py  recordings folder, settings, output folder
   │       ├── preview.py       the live example in the setup dialog
   │       ├── plots.py         the image with ROI and electrode, and the trace
   │       ├── strip.py         the strip of cards, one per recording
   │       └── window.py        the ROI Selection window
   ├── tests/                   run with: python -m pytest
   └── docs/                    this documentation

The analysis (``detection.py``, ``selections.py``, ``recordings.py``,
``labels.py`` and everything in ``evoked/``) does not import the GUI, so it
can be used from scripts and notebooks. For example, to run an evoked
analysis without the window:

.. code-block:: python

   from ema.evoked.analysis import Analysis, run
   from ema.evoked.protocol import Protocol
   from ema.evoked.workbook import write_workbooks
   from ema.roi_selection import Selections

   analysis = Analysis.open("C:/Users/you/EMA results/Evoked 2P")
   analysis.only_folders_with = ["input output"]
   run(analysis, Protocol.load("my protocol.json"), Selections.load("roi_selections.json"))
   analysis.save()
   write_workbooks(analysis)

Setting up
----------

.. code-block:: bat

   python -m pip install -r requirements-dev.txt
   python -m pytest

The tests make their own small synthetic recordings with a known release
centre and electrode, so they need no real data. The GUI tests run without
a screen.

Adding a setting
----------------

Add one entry to ``RoiSettings`` in ``ema/roi_selection/settings.py`` and
use it in ``detection.py``. The setup dialog with its live example, the ROI
file and the tables of this documentation pick it up by themselves. ROI files written before the
setting existed still load: a missing setting takes its default.

Adding a kinetic or spatial measure
-----------------------------------

The measures are listed once, in ``ema/evoked/metrics.py``. To add one:

1. Add a ``Metric`` to ``KINETIC`` or ``SPATIAL``: its name, unit, group and
   one-line definition.
2. Describe it in full in ``ema/evoked/metric_details.py``: its formula, how
   it is computed, when it is empty, what it reflects and what to be careful
   of. A test fails until every measure of the catalogue is described there.
3. Compute it in ``kinetics.py`` (in ``kinetics``) or ``spatial.py`` (in
   ``measure_spatial``), under the same name.
4. Add a test with a known answer to ``tests/test_evoked_measures.py``.

The check lists of the configurator, the list of what a protocol measures,
protocol files, the tables in this documentation and the measure reference
page follow by themselves.

Changing a built-in protocol
----------------------------

The built-in protocols are written as code in ``ema/evoked/presets.py``, so
that the tests can check their numbers. After changing that file, run

.. code-block:: bat

   python -m ema.evoked.presets

to write the files in ``ema/evoked/presets``. A test fails while the files
and the code disagree.

``tests/test_evoked_measures.py`` checks that the built-in protocols give
exactly the numbers of the earlier EMA programs, using their formulas from
the EMA V3 handoff folder next to the program (or the folder named in the
environment variable ``EMA_V2_DIR``). Without that folder those tests are
skipped.

Adding a package to the start window
------------------------------------

``PACKAGES`` in ``ema/launcher.py`` lists the packages. Give the package a
function that opens its window and returns it (or returns ``None`` if the
user cancels), and put that function in the list in place of ``None``. The
window needs a ``closed`` signal, which brings the start window back.

Building this documentation
---------------------------

.. code-block:: bat

   python docs/make_figures.py
   python docs/make_evoked_figures.py
   python docs/make_screenshots.py
   python -m sphinx docs docs/_build/html

The first three commands redraw the figures and screenshots from the sample
recordings (pass their folder as an argument if it is not found). They are only needed after a change to the detection or to
the windows; the pictures are stored in ``docs/figures`` and
``docs/screenshots``. The *Documentation* button of the start window opens
``docs/_build/html/index.html``.
