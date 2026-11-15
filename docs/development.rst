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
   │   ├── user_settings.py     remembers the last folders used
   │   └── roi_selection/
   │       ├── settings.py      every setting: default, label, help text
   │       ├── detection.py     the automatic ROI and electrode (numpy only, no GUI)
   │       ├── selections.py    the ROI file
   │       ├── setup_dialog.py  recordings folder, settings, output folder
   │       ├── plots.py         the image with ROI and electrode, and the trace
   │       └── window.py        the ROI Selection window
   ├── tests/                   run with: python -m pytest
   └── docs/                    this documentation

The analysis (``detection.py``, ``selections.py``, ``recordings.py``) does
not import the GUI, so it can be used from scripts and notebooks.

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
use it in ``detection.py``. The setup dialog, the ROI file and the tables of
this documentation pick it up by themselves. ROI files written before the
setting existed still load: a missing setting takes its default.

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
   python docs/make_screenshots.py
   python -m sphinx docs docs/_build/html

The first two commands redraw the figures and screenshots from the sample
recordings of the EMA V3 handoff (pass another folder as an argument if they
are elsewhere). They are only needed after a change to the detection or to
the windows; the pictures are stored in ``docs/figures`` and
``docs/screenshots``. The *Documentation* button of the start window opens
``docs/_build/html/index.html``.
