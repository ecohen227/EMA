The ROI file
============

ROI Selection saves everything in one file, ``roi_selections.json``, in the
output folder. The other EMA packages read this file to know where to
measure and which recordings to leave out. It is plain text (JSON): you can
open it in any text editor, but there should be no need to edit it by hand.

The file is rewritten after every change. A new file is written completely
before it replaces the old one, so a crash cannot leave half a file behind.

What is in it
-------------

.. code-block:: json

   {
     "format": "EMA ROI selections",
     "format_version": 1,
     "ema_version": "3.0.0a1",
     "saved": "2026-11-14 19:42:10",
     "recordings_folder": "C:/Users/you/Recordings",
     "folder_filter": {"only_with": ["input"], "skip_with": ["4ap", "wash"]},
     "settings": {
       "roi_radius_px": 20,
       "detection_files": ["200uA", "300uA"],
       "...": "every setting, by the name given on the settings page"
     },
     "folders": {
       "F5341/CTRL 2H/Slice 1/input output": {
         "image_shape": [128, 128],
         "roi": {"x": 67, "y": 78, "radius_px": 20, "source": "automatic"},
         "automatic_roi": {
           "x": 67, "y": 78,
           "peak_response_percent": 93.94,
           "files": ["200uA.tif", "300uA.tif"]
         },
         "electrode": {
           "source": "automatic",
           "pixels": 765,
           "rows": "59:2-3 60:1-4 61:0-6 62:0-37 63:0-41 ..."
         },
         "flagged_files": {"50uA.tif": "no response"},
         "reviewed": true
       }
     }
   }

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Entry
     - Meaning
   * - ``recordings_folder``
     - The recordings folder the selections were made in.
   * - ``folder_filter``
     - The words that chose the folders: a folder is used when its path
       contains one of ``only_with`` (or ``only_with`` is empty) and none of
       ``skip_with``.
   * - ``settings``
     - The settings in use. See :doc:`settings` for the names.
   * - ``folders``
     - One entry per recording folder. The name is the path of the folder
       inside the recordings folder, with ``/`` between the parts. Folders
       that were never opened or detected, or that the folder filter leaves
       out, have no entry.
   * - ``image_shape``
     - Rows and columns of the recordings.
   * - ``roi``
     - Centre (``x``, ``y``) and radius of the ROI in pixels. ``source`` is
       ``automatic``, or ``manual`` once the ROI was moved by hand.
   * - ``automatic_roi``
     - Where the automatic detection put the ROI, the response there, and
       the recordings whose mean it was found on. Kept even when the ROI is
       moved. It is ``null`` for a folder that was adjusted by hand and is
       waiting to be detected again after a settings change.
   * - ``electrode``
     - The electrode mask. ``source`` is ``automatic`` or ``manual``,
       ``pixels`` is its area, ``rows`` lists its pixels (see below).
   * - ``flagged_files``
     - The flagged recordings, each with its reason (which may be empty).
   * - ``reviewed``
     - ``true`` once *Accept and next* was pressed on the folder. It goes
       back to ``false`` for every folder when a setting is changed.

Positions
---------

``x`` is the column and ``y`` the row of a pixel, both counted from 0 at the
top left of the image. A pixel belongs to the ROI when its distance to the
centre is at most the radius: (column − x)² + (row − y)² ≤ radius².

The electrode mask is written as runs of pixels. ``62:0-37`` means: in row
62, columns 0 to 37 (both included) are under the electrode. A row with two
separate runs appears twice. An empty text means no mask.

Reading the file from Python
----------------------------

.. code-block:: python

   from ema.recordings import list_recordings, load_stack
   from ema.roi_selection import Selections

   selections = Selections.load("C:/Users/you/EMA results/roi_selections.json")

   for name, selection in selections.folders.items():
       folder = selections.recordings_folder / name
       roi = selection.roi_mask()                 # True inside the ROI
       electrode = selection.electrode_mask       # True under the electrode
       for path in list_recordings(folder):
           if selection.is_flagged(path.name):
               continue
           stack = load_stack(path)               # (frames, rows, columns)
           trace = stack[:, roi].mean(axis=1)     # mean brightness in the ROI

``selection.roi_mask() & ~selection.electrode_mask`` gives the ROI without
the pixels hidden by the electrode. Whether to leave those pixels out is a
choice of the analysis, not of ROI Selection: the trace shown in the ROI
Selection window uses the whole circle.

The classes are described in :doc:`../reference`.
