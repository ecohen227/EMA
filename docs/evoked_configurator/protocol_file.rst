The protocol file
=================

A protocol is one JSON file. Your protocols are kept in the ``protocols``
folder of the EMA program folder, one file per protocol, named after it;
the built-in ones are in ``ema/evoked/built_in``. The files are plain text
and can be read in any editor, but use the configurator to change them: it
checks every change.

An example, the built-in 2P protocol:

.. code-block:: json

   {
     "format": "EMA evoked protocol",
     "format_version": 1,
     "name": "2P paired pulse",
     "description": "Two pulses 4 s apart, …",
     "sampling_interval_ms": 4.849,
     "trace": "brightness",
     "recordings": {
       "measure": "every stimulated recording",
       "unstimulated_partner": "recorded right after",
       "condition": {"name": "Current", "unit": "µA"},
       "skip_words": ["red", "test"],
       "windows_follow_condition": false,
       "list": []
     },
     "baselines": {"B1": [81, 93], "B2": [904, 925]},
     "pulses": [
       {"name": "P1", "stimulus": 103, "peak": [83, 205], "baseline": "B1"},
       {"name": "P2", "stimulus": 928, "peak": [904, 1125], "baseline": "B2"}
     ],
     "comparisons": [{"name": "PPR", "pulse": "P2", "relative_to": "P1", "as": "ratio"}],
     "fits": [{"name": "Tau", "kind": "single", "after": "P1", "start": 4, "length": 412}],
     "kinetics": {"measures": [], "pulses": null, "smoothing_frames": 3},
     "spatial": {"measures": [], "pulses": ["P1"], "near_to_far": [], "settings": {"frames_before_peak": 1, "…": "…"}},
     "slice_summary": {"statistics": ["min", "max", "mean"], "condition_range": [100.0, 400.0], "baseline_spread": true,
                       "condition_fits": []}
   }

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Entry
     - Meaning
   * - ``sampling_interval_ms``
     - The time between two frames.
   * - ``trace``
     - ``"brightness"`` or ``"ratio to unstimulated"``.
   * - ``recordings.measure``
     - ``"every stimulated recording"`` or ``"listed recordings"``.
   * - ``recordings.unstimulated_partner``
     - How a stimulated recording finds its unstimulated partner:
       ``"recorded right after"`` (by the time stamps), ``"as listed"`` (in
       ``recordings.list``) or ``"none"``. A file without this entry is read
       as ``"as listed"`` when its trace is ``"ratio to unstimulated"`` and
       as ``"none"`` otherwise.
   * - ``recordings.condition``
     - The name and unit of what tells the recordings of a slice apart.
   * - ``recordings.skip_words``
     - Recordings with one of these words in their name are not measured.
   * - ``recordings.windows_follow_condition``
     - ``true`` when changing a listed recording's condition (a delay in ms)
       moves its own windows by as much. Only used while editing.
   * - ``recordings.list``
     - The listed recordings: ``file``, ``unstimulated`` (its partner, or
       ``""`` for the one recorded right after it),
       ``condition``, and for each window set per recording its timing under
       ``baselines`` (``[start, end]``) or ``pulses`` (``stimulus`` and
       ``peak``).
   * - ``baselines``
     - Each baseline window as ``[start, end]`` in frames, end not included,
       or ``"per recording"``.
   * - ``pulses``
     - Each pulse: its ``name``, its ``stimulus`` frame (or ``null``), its
       ``peak`` window and the name of its ``baseline``. A pulse set per
       recording has ``"per recording"`` as its stimulus and peak.
   * - ``comparisons``
     - ``pulse``'s response ÷ ``relative_to``'s, ``as`` ``"ratio"`` or
       ``"percent"``.
   * - ``fits``
     - ``kind``: ``"single"`` or ``"double"``; ``after``: the pulse whose
       maximum the fit starts after (``null`` for a fixed frame); ``start``:
       frames after that maximum (or the first frame); ``length``: frames.
   * - ``kinetics``
     - ``measures``: names from the kinetic table in :doc:`measures`;
       ``pulses``: the pulses they are measured on (``null`` for every pulse);
       ``smoothing_frames``.
   * - ``spatial``
     - ``measures``: names from the spatial table in :doc:`measures`;
       ``pulses``: the pulses they are measured on; ``near_to_far``: the
       comparisons also measured as near-to-far indices; ``settings``: the
       settings of the maps and rings (see below).
   * - ``slice_summary``
     - ``statistics`` (any of ``"min"``, ``"max"``, ``"mean"``),
       ``condition_range`` (``[low, high]`` or ``null``),
       ``baseline_spread`` (``true`` or ``false``) and ``condition_fits``:
       each with its ``name``, the per-recording ``measure`` it is fitted to,
       its ``model`` (``"recovery"`` or ``"saturation"``) and, for a
       recovery, the ``plateau`` it is fixed at (``null`` to fit it).

Frame 0 is the second frame of the TIFF: the first is dropped when a
recording is read.

The settings of the maps and rings under ``spatial.settings``, with their
names on the *Spatial* tab (see :doc:`measures` for what each does):

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Name in the file
     - Setting
   * - ``frames_before_peak``
     - Frames before the peak
   * - ``frames_from_peak``
     - Frames from the peak on
   * - ``smoothing_px``
     - Spatial smoothing
   * - ``pixel_um``
     - Pixel size
   * - ``max_radius_um``
     - Largest ring
   * - ``integrate_um``
     - Integration radius
   * - ``tail_from_um``
     - Tail radius
   * - ``region_um``
     - Region radius
   * - ``near_from_um``, ``near_to_um``
     - Near band from, up to
   * - ``far_from_um``, ``far_to_um``
     - Far band from, up to
   * - ``exclude_electrode``
     - Leave out the electrode
   * - ``follow_ms``
     - Follow the decay for at most

Reading a protocol from Python
------------------------------

.. code-block:: python

   import numpy as np
   from ema.evoked import Protocol, measure

   protocol = Protocol.load("protocols/My protocol.json")

   # every measure the protocol produces, with its unit and definition
   for item in protocol.measures():
       print(item.name, item.unit, item.explanation)

   # measure one trace: the ROI brightness of a stimulated recording, corrected with its partner's
   from ema.evoked.traces import make_trace
   trace = make_trace(protocol, np.load("stimulated.npy"), np.load("unstimulated.npy"))
   measurement = measure(protocol, trace)
   print(measurement.values["P1 response"], measurement.values["PPR"])

   # the spatial measures need the whole movie, the ROI centre and the electrode mask
   from ema.evoked.spatial import measure_spatial
   from ema.evoked.traces import make_movie
   movie = make_movie(protocol, stimulated_movie, partner_movie)  # both (frames, rows, columns)
   spatial = measure_spatial(protocol, movie, (67, 78), electrode_mask, measurement)
   print(spatial.values)

For a listed recording, pass it too, so that windows set per recording are
known: ``measure(protocol, trace, protocol.recordings[0])``. The classes and
functions are described in :doc:`../reference`.
