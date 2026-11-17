The detector file
=================

A detector is saved as a JSON file named after it: the built-in one in
``ema/spontaneous/built_in``, your own in the ``detectors`` folder of EMA.
It can be read and written by other programs. The Standard detector,
shortened:

.. code-block:: json

   {
     "format": "EMA spontaneous detector",
     "format_version": 1,
     "name": "Standard detector",
     "description": "…",
     "recordings": {"searched": "unstimulated recordings", "skip_words": ["red"]},
     "settings": {
       "frame_ms": 4.849, "pixel_um": 16.0, "first_frames": 20, "last_frames": 10,
       "rise_ms": 12.0, "decay_ms": 200.0, "before_ms": 100.0, "after_ms": 600.0, "line_baseline": true,
       "blur_um": 128.0, "remove_field": true,
       "event_z": 8.0, "region_z": 3.0, "end_trim_ms": 320.0,
       "sign_flip": true, "time_reversed": true,
       "near_um": 480.0, "site_um": 100.0, "together_ms": 1000.0, "fit_radius_um": 400.0, "good_fit_r2": 0.2, "max_width_um": 380.0,
       "brightness_frames": [10, 95], "block_px": 4, "dark_fraction": 0.3, "electrode_fraction": 0.5,
       "bleach_order": 4, "despike_frames": 3,
       "echo_rule": true, "echo_ms": 533.0, "echo_um": 256.0, "echo_ratio": 1.0
     },
     "measures": {
       "per_event": ["onset", "strength", "fitted peak", "width", "…"],
       "per_recording": ["events", "searched time", "rate", "…"],
       "per_slice": ["events", "searched time", "rate", "…"],
       "per_slice_of_events": {"measures": ["fitted peak", "width", "…"], "statistics": ["median"]}
     }
   }

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entry
     - Meaning
   * - ``recordings.searched``
     - Which recordings of a folder are searched: the unstimulated ones,
       named ``no`` and a number.
   * - ``recordings.skip_words``
     - Recordings with one of these words in their name are not searched.
   * - ``settings``
     - Every setting, by its name in the file. The example above lists them
       all, one section of :doc:`settings` per line, in the same order:
       Movie, Event shape, Spatial filter, Detection, Controls, Measuring,
       Tissue, Signal, Echoes. A setting missing from a file takes its
       default.
   * - ``measures.per_event``, ``per_recording``, ``per_slice``
     - The chosen measures, by their names in :doc:`measure_reference`.
   * - ``measures.per_slice_of_events``
     - The event measures summarised per slice, and by which statistics
       (``median``, ``mean``, ``min``, ``max``): ``width median`` and so on.
