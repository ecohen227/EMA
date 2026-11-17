Code reference
==============

The modules that do the measuring, by package. None of them needs the GUI.

Shared
------

Recordings
~~~~~~~~~~

.. automodule:: ema.recordings
   :members:

Settings and measures
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.definitions
   :members: setting, Settings, Measure

Libraries of protocols and detectors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.library
   :members: Library, Entry, file_name

Kept results
~~~~~~~~~~~~

.. automodule:: ema.kept_results
   :members: KeptAnalysis, Plan, FolderResult, RecordingResult, fingerprint, why_not_measured, write_json

Labels from folder names
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.labels
   :members: Label, LabelSet, FolderLabels, NearMiss, default_labels, words, find

What both analyses' Excel files share
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.excel
   :members: Slice, slices, groups, save_workbooks, column_table, grouped_table, sheet_names, TablesLocked

ROI Selection
-------------

Detection
~~~~~~~~~

.. automodule:: ema.roi_selection.detection
   :members:

The ROI file
~~~~~~~~~~~~

.. automodule:: ema.roi_selection.selections
   :members: FolderSelection, Selections, mask_runs, mask_to_text, text_to_mask

Settings
~~~~~~~~

.. autoclass:: ema.roi_selection.settings.RoiSettings
   :members: problems

Evoked responses
----------------

Protocols
~~~~~~~~~

.. automodule:: ema.evoked.protocol
   :members: Protocol, Window, Pulse, PulseTiming, Recording, Comparison, Fit, ConditionFit, Column, ProtocolError

The catalogue of kinetic and spatial measures
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.evoked.catalogue
   :members: SpatialSettings

The measured trace and the unstimulated partner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.evoked.traces
   :members: find_partner, make_trace, make_movie, combine, correction_window

Measuring
~~~~~~~~~

.. automodule:: ema.evoked.measures
   :members: Measurement, measure, response, compare, fit_decay, summarise, fit_across_conditions

Kinetic measures
~~~~~~~~~~~~~~~~

.. automodule:: ema.evoked.kinetics
   :members: response_trace, kinetics, crossing, vertex

Spatial measures
~~~~~~~~~~~~~~~~

.. automodule:: ema.evoked.spatial
   :members: SpatialResult, Decay, measure_spatial, response_map, ring_profile, footprint, centroid_and_unevenness, near_to_far, release_spread, decay_course, decay_measures

The template
~~~~~~~~~~~~

.. automodule:: ema.evoked.template
   :members: Template

The built-in protocols and the library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.evoked.presets
   :members: LIBRARY, PRESETS, write_presets

Running a protocol on an ROI file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.evoked.analysis
   :members: Analysis, plan, run, measure_folder, folder_fingerprint, choices

The Excel files
~~~~~~~~~~~~~~~

.. automodule:: ema.evoked.workbook
   :members: write_workbooks

Spontaneous events
------------------

The detector's settings
~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: ema.spontaneous.settings.DetectorSettings
   :members: frames, pixels, problems

The catalogue of measures
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.spontaneous.catalogue

The detector
~~~~~~~~~~~~

.. automodule:: ema.spontaneous.detection
   :members: Detection, detect, resting_brightness, tissue_mask, bleach_corrected, despiked, dff, pixel_noise, median_of_rows, kernel, template, time_filter, space_filter, zscore, connected, regions, drop_echoes, z_movie, signed_regions, counted

The measures
~~~~~~~~~~~~

.. automodule:: ema.spontaneous.measures
   :members: measure_events, event_trace, time_course, peak_map, measure_recording, summarise_slice, summarise_events, clustering_index

The detector file
~~~~~~~~~~~~~~~~~

.. automodule:: ema.spontaneous.detector
   :members: Detector, DetectorError

The built-in detector and the library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.spontaneous.presets
   :members: LIBRARY, PRESETS, standard_detector, write_presets

Searching the folders of a recordings folder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: ema.spontaneous.analysis
   :members: Analysis, Recordings, plan, run, search_recording, automatic_roi, default_workers, detection_part, one_thread_each

The Excel files
~~~~~~~~~~~~~~~

.. automodule:: ema.spontaneous.workbook
   :members: write_workbooks, slice_values
