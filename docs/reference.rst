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
