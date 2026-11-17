Extending EMA
=============

This page shows where each kind of change goes. Each recipe lists every
place to touch; the tests named in it fail when one of them is forgotten.
Run ``python -m pytest`` after each change.

How a measurement flows through EMA
-----------------------------------

.. code-block:: text

   recordings (TIFF, read only)
       │  ema/recordings.py: list_recordings, load_stack
       ▼
   ROI file (ROI Selection) ─────────┐   protocol or detector (configurators)
       │                             │        │
       ▼                             ▼        ▼
   ema/evoked/analysis.py run()   ema/spontaneous/analysis.py run()
       │ per recording: traces.py → measures.py → kinetics.py, spatial.py
       │ per recording: detection.py → measures.py
       ▼
   kept results (ema/kept_results.py): <output folder>/evoked_analysis.json or spontaneous_analysis.json
       │
       ▼
   Excel files (ema/evoked/workbook.py, ema/spontaneous/workbook.py, ema/excel.py)

What is measured is listed once, in a *catalogue* (``catalogue.py``), and
described in full once (``measure_details.py``). The configurators' check
lists, the columns of the Excel files and the measure references of this
documentation are all built from those two files. Settings work the same way:
each is declared once with ``setting()`` (``ema/definitions.py``), and the
forms, the files and the settings tables follow.

Add an evoked kinetic measure
-----------------------------

Kinetic measures describe the time course of one pulse's response, such as
``P1 half-decay``.

1. ``ema/evoked/catalogue.py``: add a ``Measure`` to ``KINETIC``: its key
   (the name in the tables, after the pulse's name), unit, group and a
   one-line definition (``{pulse}`` stands for the pulse's name).
2. ``ema/evoked/kinetics.py``: compute it in ``kinetics()``, in the
   ``values`` dict, under the same key. Values that cannot be measured are
   ``np.nan``.
3. ``ema/evoked/measure_details.py``: describe it in full in
   ``KINETIC_DETAILS``: formula, how it is computed, when it is empty, what it
   reflects, what to be careful of.
4. ``tests/test_evoked_measures.py``: a test with a trace whose answer you
   know.

Forgetting step 2 or 3 makes a test fail (every catalogue entry must be
computed and described).

Add an evoked spatial measure
-----------------------------

Spatial measures describe how a pulse's response spreads over the slice
around the ROI centre.

1. ``ema/evoked/catalogue.py``: add a ``Measure`` to ``SPATIAL``.
2. ``ema/evoked/spatial.py``: compute it in one of the four steps
   (``footprint``, ``centroid_and_unevenness``, ``release_spread``,
   ``decay_measures``) and add its key to that step's key list at the top of
   the file (``FOOTPRINT_KEYS``, …). The slower steps run only when one of
   their keys is chosen.
3. ``ema/evoked/measure_details.py``: describe it in ``SPATIAL_DETAILS``.
4. A test in ``tests/test_evoked_measures.py``.

``tests/test_structure.py`` fails until the key is in exactly one step's
list, and reading a value that no step computed raises an error rather than
leaving an empty column.

Add a spontaneous-event measure
-------------------------------

1. ``ema/spontaneous/catalogue.py``: add a ``Measure`` to ``EVENT``,
   ``RECORDING`` or ``SLICE``.
2. ``ema/spontaneous/measures.py``: compute it:

   * per event: in ``measure_events`` (or in ``_time_course`` / ``_fit_width``,
     which also list the keys they leave empty when they cannot measure);
   * per recording: in ``measure_recording``;
   * per slice: in ``summarise_slice``.

3. ``ema/spontaneous/measure_details.py``: describe it in ``EVENT_DETAILS``,
   ``RECORDING_DETAILS`` or ``SLICE_DETAILS``.
4. If the standard detector should report it, add it to the lists in
   ``ema/spontaneous/presets.py`` and run ``python -m ema.spontaneous.presets``.
5. Raise ``RESULTS_VERSION`` in ``ema/spontaneous/analysis.py`` by one, so
   folders searched before get the new measure on the next run.
6. A test in ``tests/test_spontaneous.py``.

Add a setting
-------------

Settings are declared in a settings class: ``RoiSettings``
(``ema/roi_selection/settings.py``), ``SpatialSettings``
(``ema/evoked/catalogue.py``) or ``DetectorSettings``
(``ema/spontaneous/settings.py``).

1. Add a field made with ``setting(default, section, label, help, kind, unit,
   …)``. The kind is ``int`` or ``float`` (give ``minimum``, ``maximum`` and,
   for a float, ``step``), ``bool``, ``frames`` (a window ``[first, last)``),
   ``names`` (words separated by commas) or ``choice`` (give ``choices``).
   Mark it ``advanced=True`` to show it under Advanced. The section must be
   one of the class's sections (``GROUPS`` for the detector).
2. Use it where it is needed (``detection.py``, ``measures.py``,
   ``spatial.py``, …).
3. If it changes any number, raise ``RESULTS_VERSION`` of the analysis it
   affects.

The form with its "changed from the default" notes, the files, and the tables
of this documentation follow by themselves. Files saved before the setting
existed still open: a missing setting takes its default.
``tests/test_structure.py`` checks that every setting has a label, a help text
and a kind the forms know.

Add a feature to evoked protocols
---------------------------------

A protocol feature is something a user sets in the Evoked Analysis
Configurator that changes what is measured, such as a new kind of window or
comparison. It touches more places, because a protocol is edited, checked,
saved and measured:

1. ``ema/evoked/protocol.py``:

   * the field on ``Protocol`` (or a new small dataclass, like ``Fit``);
   * ``measures()``: the columns it produces (name, unit, explanation);
   * ``problems()``: what can be wrong with it, in plain sentences;
   * ``names()`` if it has a name of its own (names must be unique), and
     ``rename()`` if other parts refer to it by name;
   * ``to_dict()`` and ``from_dict()``: how it is saved and read back, with a
     default for files saved before it existed.

2. ``ema/evoked/measures.py``: compute it in ``measure()`` (per recording) or
   ``summarise()`` (per slice).
3. ``ema/evoked_configurator/``: a row or tab to edit it
   (``editors.py`` or ``measure_editors.py``), and, if it has a window on the
   trace, a handle in ``plot.py``.
4. ``ema/evoked/measure_details.py``: describe its columns (``BASIC`` or
   ``SLICE``).
5. ``tests/test_evoked_protocol.py``: a round trip through a file
   (``Protocol.from_dict(p.to_dict()) == p``) with the feature set, and its
   problems; ``tests/test_evoked_measures.py``: its numbers.
6. Raise ``RESULTS_VERSION`` in ``ema/evoked/analysis.py``.

The Excel files, the slice summaries, the configurator's table of what will be
measured and the re-measuring of kept folders follow by themselves.

Add a default label
-------------------

``default_labels()`` in ``ema/labels.py`` lists the labels a new user starts
with: a ``Label`` with values and their spellings, or with number patterns
such as ``"Slice #"``. Users who changed their labels keep theirs.

Add a built-in protocol or detector
-----------------------------------

Write it as a function in ``ema/evoked/presets.py`` or
``ema/spontaneous/presets.py``, add it to ``PRESETS``, and run
``python -m ema.evoked.presets`` (or ``ema.spontaneous.presets``) to write its
file in ``built_in/``. A test fails while the files and the code disagree.

Add a package to the start window
---------------------------------

``WORKFLOWS`` in ``ema/launcher.py`` lists the packages under their heading,
in the order they are used: a name, one sentence about what it does, and a
function that opens its window (or returns ``None`` when the user cancels).
The window needs a ``closed`` signal, which brings the start window back.
Packages are found by setuptools by themselves, so ``pyproject.toml`` needs no
change. ``tests/test_gui.py`` checks the start window's list.

File formats
------------

Every file EMA writes is JSON with a ``format`` and a ``format_version``:

.. list-table::
   :header-rows: 1

   * - File
     - Written by
     - Read with
   * - ``roi_selections.json``
     - ROI Selection
     - ``Selections.load``
   * - protocol files
     - Evoked Analysis Configurator
     - ``Protocol.load``
   * - detector files
     - Spontaneous Event Configurator
     - ``Detector.load``
   * - kept results
     - the analyses, in their output folder
     - ``Analysis.load``

Each ``load`` raises ``OSError`` or ``ValueError`` only. Raise
``FORMAT_VERSION`` only when an older EMA could no longer read a new file
correctly; adding a field with a default needs no new version.
