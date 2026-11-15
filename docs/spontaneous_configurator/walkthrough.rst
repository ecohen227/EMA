The configurator, step by step
==============================

1. **Choose a detector** in the bar at the top: *Detector v5* or one of
   your own.
2. **Choose an example folder**: a folder of recordings with unstimulated
   recordings in it, such as an ``input output`` folder. Choose the
   **ROI file** of ROI Selection too, so the release centre (ROI centre) and
   the electrode are the reviewed ones; without it they are found
   automatically from the folder's stimulated recordings. Nothing is ever
   written into the folder.
3. The first unstimulated recording is searched at once (a few seconds).
   Choose another under **Recording**. The line above the plots says how
   many events were found in how much searched time, with the sign-flipped
   and time-reversed counts.
4. **Look at the events.** The left plot shows each pixel's largest z over
   the recording: events are circled and numbered, the electrode is outlined
   in cyan, and + marks the release centre. Click an event, or its row in
   the table, to see its **peak map** (with the fitted Gaussian's
   half-maximum circle) and its **pooled trace** (with the detected onset
   dashed).
5. **Change the detector** on the tabs:

   * **1 Detector**: the description, the words that exclude a recording
     (``red`` by default), and every setting, in sections that open on a
     click. A closed section says how many of its settings differ from
     detector v5. *Restore the defaults* brings them all back.
   * **2 Per event**: the measures of each event, with *All* and *None*.
   * **3 Per recording and slice**: the measures of each recording and of
     each slice (all searched recordings of a folder), and which event
     measures are summarised per slice, by their median, mean, smallest or
     largest value.

   A change to the **Measuring** settings or to the chosen measures shows at
   once. Any other setting changes what is found: press **Search** to see
   it on the example.
6. **Save** it under a name of your own. Your detectors are kept in the
   ``detectors`` folder of EMA. *Export…* saves a copy anywhere, to share
   it; *Import…* adds one to the library.

The table shows the chosen per-event measures of every event, and the line
above it the chosen per-recording measures. Per-slice measures need every
recording of a slice, so they are not shown on one example.

Hover over any setting or measure for its definition. :doc:`settings` lists
the settings, and :doc:`measure_reference` gives every measure in full.
