Code reference
==============

Recordings
----------

.. automodule:: ema.recordings
   :members:

ROI Selection: detection
------------------------

.. automodule:: ema.roi_selection.detection
   :members:

ROI Selection: the ROI file
---------------------------

.. automodule:: ema.roi_selection.selections
   :members: FolderSelection, Selections, mask_runs, mask_to_text, text_to_mask

ROI Selection: settings
-----------------------

.. autoclass:: ema.roi_selection.settings.RoiSettings
   :members: to_dict, from_dict, problems

Evoked: protocols
-----------------

.. automodule:: ema.evoked.protocol
   :members: Protocol, Window, Pulse, PulseTiming, Recording, Comparison, Fit, ConditionFit, Measure, ProtocolError

Evoked: the measured trace and the unstimulated partner
-------------------------------------------------------

.. automodule:: ema.evoked.traces
   :members: find_partner, make_trace, make_movie, combine, correction_window

Evoked: measuring
-----------------

.. automodule:: ema.evoked.measures
   :members: Measurement, measure, response, compare, fit_decay, summarise, fit_across_conditions

Evoked: the catalogue of kinetic and spatial measures
-----------------------------------------------------

.. automodule:: ema.evoked.metrics
   :members: Metric, SpatialSettings

Evoked: kinetic measures
------------------------

.. automodule:: ema.evoked.kinetics
   :members: response_trace, kinetics, crossing, vertex

Evoked: spatial measures
------------------------

.. automodule:: ema.evoked.spatial
   :members: SpatialResult, Decay, measure_spatial, response_map, ring_profile, footprint, centroid_and_unevenness, near_to_far, release_spread, decay_course, decay_measures

Evoked: the template
--------------------

.. automodule:: ema.evoked.template
   :members: Template

Evoked: the protocol library
----------------------------

.. automodule:: ema.evoked.library
   :members: Entry, entries, save, delete, is_taken, file_name

Spontaneous events: the detector's settings
-------------------------------------------

.. autoclass:: ema.spontaneous.settings.DetectorSettings
   :members: frames, pixels, to_dict, from_dict, problems

Spontaneous events: the detector
--------------------------------

.. automodule:: ema.spontaneous.detection
   :members: Detection, detect, resting_brightness, tissue_mask, bleach_corrected, despiked, dff, pixel_noise, kernel, template, time_filter, space_filter, zscore, regions, drop_echoes, z_movie, signed_regions, counted

Spontaneous events: the measures
--------------------------------

.. automodule:: ema.spontaneous.measures
   :members: Measure, measure_events, event_trace, time_course, peak_map, measure_recording, summarise_slice, clustering_index

Spontaneous events: the detector file and library
-------------------------------------------------

.. automodule:: ema.spontaneous.detector
   :members: Detector, DetectorError, detector_v5, entries, save_in_library, is_taken, file_name, write_presets

Spontaneous Event Analysis: searching the folders of a recordings folder
------------------------------------------------------------------------

.. automodule:: ema.spontaneous.analysis
   :members: Analysis, FolderResult, RecordingResult, Recordings, plan, run, search_recording, automatic_roi, default_workers, detection_part

Spontaneous Event Analysis: the Excel files
-------------------------------------------

.. automodule:: ema.spontaneous.workbook
   :members: write_workbooks, slice_values, slice_measures

What both analyses' Excel files share
-------------------------------------

.. automodule:: ema.excel
   :members: Slice, slices, groups, save_workbooks, column_table, grouped_table, TablesLocked

Evoked Analysis: running a protocol on an ROI file
--------------------------------------------------

.. automodule:: ema.evoked.analysis
   :members: Analysis, FolderResult, RecordingResult, Plan, plan, run, measure_folder, folder_fingerprint, choices

Evoked Analysis: the Excel files
--------------------------------

.. automodule:: ema.evoked.workbook
   :members: write_workbooks, TablesLocked

Labels from folder names
------------------------

.. automodule:: ema.labels
   :members: Label, LabelSet, FolderLabels, NearMiss, default_labels, words, find
