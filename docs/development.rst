Working on EMA
==============

The code is meant to be read by the people who use it. It favours plain
functions, full words for names, and short files with one job each.
:doc:`extending` shows, step by step, how to add a measure, a setting or a
feature.

Layout
------

The measuring lives in packages named after a topic (``evoked``,
``spontaneous``, ``roi_selection``); they never import the GUI, so they work
in scripts, notebooks and the analyses' worker processes (a test checks
this). The windows live in packages named after the tool on the start window
(``evoked_configurator``, ``evoked_analysis``, …).

.. code-block:: text

   EMA/
   ├── EMA.pyw                  double-click to start
   ├── ema/
   │   ├── app.py               starts Qt, shows unexpected errors in a dialog, opens the start window
   │   ├── launcher.py          the start window: the packages, in the order they are used
   │   ├── paths.py             where saved protocols and detectors, the docs and the remembered choices are
   │   ├── recordings.py        finding and reading TIFF movies (read-only); the camera's defaults; skip words
   │   ├── definitions.py       how settings and measures are declared (setting(), Settings, Measure)
   │   ├── library.py           the library of protocols or detectors: built-in and saved
   │   ├── kept_results.py      what an analysis keeps in its output folder; what a new run measures again
   │   ├── excel.py             what both analyses' Excel files share: slices, groups, Prism tables, saving
   │   ├── labels.py            labels read from folder names, and possible typos
   │   ├── user_settings.py     remembers the last folders used
   │   ├── widgets.py           widgets every window uses: inputs, settings forms, check lists, the library bar
   │   ├── labels_editor.py     the Labels and Possible typos tabs of both analyses
   │   ├── analysis_window.py   the window both analyses share; each brings a Kind
   │   ├── blit.py              fast redrawing of things that follow the mouse
   │   ├── roi_selection/       ROI Selection
   │   │   ├── settings.py      every setting: default, label, help text
   │   │   ├── detection.py     the automatic ROI and electrode
   │   │   ├── selections.py    the ROI file
   │   │   └── window.py, setup_dialog.py, preview.py, plots.py, strip.py   its windows
   │   ├── evoked/              evoked responses: protocols and measuring
   │   │   ├── protocol.py      what a protocol holds, its checks, what it measures, and its file
   │   │   ├── catalogue.py     the kinetic and spatial measures, one line each, and the spatial settings
   │   │   ├── measure_details.py  the full description of every measure, for the measure reference
   │   │   ├── traces.py        the measured trace and movie, with the unstimulated partner
   │   │   ├── measures.py      measuring one trace with a protocol; fits; slice summaries
   │   │   ├── kinetics.py      kinetic measures of one pulse
   │   │   ├── spatial.py       response maps, rings and the spatial measures
   │   │   ├── template.py      the template every protocol can be built from
   │   │   ├── presets.py       the built-in protocols, as code, and the protocol library
   │   │   ├── built_in/        … the built-in protocols as the files EMA ships
   │   │   ├── analysis.py      running a protocol on the folders of an ROI file
   │   │   └── workbook.py      the two Excel files, laid out for Prism
   │   ├── spontaneous/         spontaneous events: the detector and measuring
   │   │   ├── settings.py      every setting of the detector: default, label, help text
   │   │   ├── catalogue.py     the event, recording and slice measures, one line each
   │   │   ├── measure_details.py  the full description of every measure, for the measure reference
   │   │   ├── detection.py     the detector, step by step
   │   │   ├── measures.py      computing the event, recording and slice measures
   │   │   ├── detector.py      the detector file: settings, skip words, chosen measures
   │   │   ├── presets.py       the built-in detector, as code, and the detector library
   │   │   ├── built_in/        … the built-in detector as the file EMA ships
   │   │   ├── analysis.py      searching the folders of a recordings folder, in parallel
   │   │   └── workbook.py      the two Excel files, laid out for Prism
   │   ├── evoked_configurator/  the Evoked Analysis Configurator window, its tabs and its plots
   │   ├── evoked_analysis/     what the evoked analysis brings to the shared window
   │   ├── spontaneous_configurator/  the Spontaneous Event Configurator window and its example folder
   │   └── spontaneous_analysis/  what the spontaneous-event analysis brings to the shared window
   ├── tests/                   run with: python -m pytest
   └── docs/                    this documentation

For example, to run an evoked analysis without the window:

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

The spontaneous analysis searches in several processes at once. On Windows
each of them starts the script again, so a script that runs it needs
``if __name__ == "__main__":`` around its main part (see
``ema/spontaneous/analysis.py``).

Setting up
----------

.. code-block:: bat

   python -m pip install -r requirements-dev.txt
   python -m pytest

The tests make their own small synthetic recordings with a known ROI centre
and electrode, so they need no real data. The window tests run without a
screen; a message box a test does not answer makes it fail rather than wait.

Rules that keep the code safe to change
---------------------------------------

* Every file EMA reads (protocols, detectors, ROI files, kept results,
  labels) is read by a ``load`` that raises only ``OSError`` or a
  ``ValueError``: callers catch those two, and a damaged file is reported,
  never a crash.
* A recording that cannot be measured is listed in the Notes sheet with the
  reason; it never stops a run.
* Built-in protocols and detectors are written as code (``presets.py``) and
  shipped as files (``built_in/``); a test fails while the two disagree. After
  changing one, run ``python -m ema.evoked.presets`` or
  ``python -m ema.spontaneous.presets``.
* Each analysis has a ``RESULTS_VERSION`` (``ema/evoked/analysis.py``,
  ``ema/spontaneous/analysis.py``). Raise it by one whenever a change to EMA
  changes any number an analysis writes: results kept in output folders are
  then measured again on the next run. Changes that only touch the windows or
  the tables' layout need no new version.
* The format of a file (``FORMAT_VERSION``) is raised only when an older EMA
  could no longer read it correctly.
* ``tests/test_evoked_measures.py`` checks that the built-in protocols give
  exactly the numbers of a reference implementation, kept outside the program
  (the folder named in the environment variable ``EMA_V2_DIR``). Without that
  folder those tests are skipped.

Building this documentation
---------------------------

.. code-block:: bat

   python docs/make_figures.py
   python docs/make_evoked_figures.py
   python docs/make_spontaneous_figures.py
   python docs/make_screenshots.py
   python -m sphinx docs docs/_build/html

The first four commands redraw the figures and screenshots from the sample
recordings (pass their folder as an argument if it is not found);
``make_screenshots.py`` also writes the example Excel files in
``docs/examples``, which the pages on the Excel files show and offer for
download. They are only needed after a change to the measuring or to the
windows; the pictures are stored in ``docs/figures`` and ``docs/screenshots``.
The tables of settings and the measure references are written from the code
each time the documentation is built (see ``docs/conf.py``). The
*Documentation* button of the start window opens ``docs/_build/html/index.html``.
