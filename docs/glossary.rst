Glossary
========

The words used in EMA's windows, tables and documentation.

.. glossary::
   :sorted:

   1/e decay
      The time a response takes to fall from its maximum to 1/e (37 %) of
      it. For a response that decays as a single exponential it equals
      :term:`τ <tau>`.

   4-AP
      4-Aminopyridine, a drug that blocks potassium channels and makes
      neurons release transmitter more often.

   baseline
      The mean of the :term:`trace` over a :term:`baseline window`, just
      before a stimulus (B1, B2, BL …). A pulse's :term:`response` is
      measured from its baseline.

   baseline window
      The frames before a stimulus whose mean is the :term:`baseline`.

   bleaching
      The slow fall of brightness during a recording: the light that
      excites the sensor also slowly destroys its fluorescence. The Evoked
      Analysis corrects it with an :term:`unstimulated partner`; the
      spontaneous-event detector divides each pixel by a smooth curve fitted
      to it over time.

   built-in
      A protocol or detector that comes with EMA. It cannot be changed or
      deleted. Change it and press *Save*: EMA asks for a new name and keeps
      your version as one of your own.

   centroid
      The centre of a :term:`response map`, each pixel weighted by its
      response.

   column table
      A table of GraphPad :term:`Prism` with one column per group and one
      value per row, for example one value per slice.

   comparison
      The response of one pulse divided by the response of another, such as
      the :term:`PPR` or P2/P1.

   condition
      What tells the recordings of a slice apart: the current, read from the
      number the file name starts with (200 for ``200uA.tif``), or a value
      the protocol lists for each recording, such as the delay of a recovery
      pulse.

   counts
      Camera units of brightness, as stored in the TIFF.

   detector
      What the Spontaneous Event Analysis searches with: the settings that
      decide how events are found, and the measures reported per event, per
      recording and per slice. Detectors are made in the Spontaneous Event
      Configurator and saved as JSON files.

   dF/F
      The change of brightness F relative to the resting brightness F0:
      (F − F0) ÷ F0, usually given in percent.

   dLight
      A genetically encoded sensor that glows more brightly when it binds
      dopamine. GRAB-DA is another family of dopamine sensors; iGluSnFR is a
      sensor for glutamate.

   echo
      The filter shaped like an event also gives a weak signal of the
      opposite sign just before and just after a real event. The
      spontaneous-event detector drops these echoes, so they are not counted
      as events.

   electrode mask
      The pixels hidden by the stimulating electrode, shown in cyan. It is
      found in ROI Selection, and can be redrawn there by hand.

   event
      In the spontaneous-event analysis: a brief, local rise of brightness
      without a stimulus, from spontaneous dopamine release.

   event threshold
      The :term:`strength` a :term:`region` must reach to count as an event,
      in × noise; 8 in the :term:`Standard detector`.

   exponential fit
      A curve A·exp(−t/τ) + C fitted to a decaying response. Its time
      constant :term:`τ <tau>` describes how fast the response decays. A
      double fit adds a second exponential, which gives a fast and a slow
      time constant.

   F0
      The resting brightness of a pixel or of the ROI: its mean brightness
      over a :term:`baseline window`.

   near band
   far band
      Two sets of :term:`rings <ring>` of a :term:`response map`: the near
      band close to the :term:`ROI centre` (0 to 160 µm by default), the far
      band farther out (400 to 640 µm by default).

   fit quality
      How much of the variation in the data a fitted curve explains (r²): 1
      is a perfect fit, 0 is no better than a flat line.

   flag
      A mark you put on a recording in ROI Selection when it fails your
      criteria, with a reason. The analyses leave flagged recordings out
      (the Spontaneous Event Analysis when it uses the ROI file).

   footprint
      The area of slice over which an evoked response spreads around the
      :term:`ROI centre`. Its width is found by fitting a :term:`Lorentzian`
      to the :term:`ring` averages of the response map.

   frame
      One image of a movie. Frame 0 in EMA is the second frame of the TIFF
      file: the first is always dropped.

   Gaussian
      The bell-shaped curve exp(−r²/2σ²). σ (sigma) is its width: at a
      distance σ from the centre it has fallen to 61 % of its peak.

   grouped table
      A table of GraphPad :term:`Prism` with one row per value of something
      (such as each current or each treatment) and, for each group, several
      columns side by side, one per slice.

   half-decay
      The time from the maximum of a response until it has fallen to half of
      it.

   half-max
      In a :term:`saturation curve`, the condition (for example the current)
      at which the response reaches half of its top.

   kept results
      The file in the output folder of an analysis, ``evoked_analysis.json``
      or ``spontaneous_analysis.json``, that holds everything about the
      analysis: what it measured with, the labels, and every result. A new
      run uses it to measure only what has changed.

   label
      A property of a slice read from its folder names, such as *Genotype*.
      A label has values (WT, HET), and each value has the spellings that
      mean it in a folder name (WT, wild type, wildtype).

   least squares
      Fitting a curve by making the sum of the squared differences between
      the curve and the data as small as possible.

   library
      The protocols, or the detectors, that EMA offers by name: the built-in
      ones and those you saved, which are kept in the ``protocols`` and
      ``detectors`` folders of EMA.

   Lorentzian
      The bell-shaped curve a ÷ (1 + (r/λ)²) + c, whose width is λ. It falls
      off more slowly far from the centre than a :term:`Gaussian`.

   median
      The middle value. Unlike the mean, it is hardly moved by a few extreme
      values.

   noise
      The random flicker of brightness from frame to frame and from pixel to
      pixel.

   output folder
      The folder a package writes its files into. It must lie outside the
      recordings folder.

   peak
      The maximum of the trace inside a pulse's :term:`peak window` (P1,
      P2 …).

   peak map
      The image of a spontaneous event at its peak, in dF/F. A
      :term:`Gaussian` fitted to it gives the event's width, fitted peak and
      centre.

   peak window
      The frames in which the peak of a pulse is looked for.

   percentage points
      The difference between two values given in percent: from −1 % to 33 %
      is 34 percentage points.

   pixel size
      The width of slice one pixel covers: 16 µm with the 4× objective.

   pooled trace
      The trace of a spontaneous event at its centre, averaged over the
      neighbouring pixels by the detector's :term:`spatial filter`. It is
      clean enough to time the event, but its peak is lower than the
      event's own.

   possible typo
      A word in a folder name that is not a spelling of a label value but
      looks like one, such as *Contrl* for CTRL. Both analyses list them on
      their *Possible typos* tab.

   PPR
      Paired-pulse ratio: the response to the second of two pulses divided by
      the response to the first.

   Prism
      GraphPad Prism, a program for graphs and statistics. EMA lays out its
      Excel sheets so they can be pasted straight into Prism tables.

   protocol
      What the Evoked Analysis measures with: which recordings, the windows
      of each pulse, and what is derived from them. Protocols are made in the
      Evoked Analysis Configurator and saved as JSON files.

   pulse
      One electrical stimulus and the response to it (P1, P2 …).

   r50
      The radius of the circle around the :term:`ROI centre` that holds half
      of the signal of a :term:`response map`.

   recording
      One TIFF movie: one trial.

   recording folder
      A folder that holds at least one recording. Each recording folder is
      one :term:`slice` in the tables.

   recordings folder
      The top folder you choose, which holds the recording folders: one
      slice, one animal or a whole study.

   recovery curve
      plateau − (plateau − start)·exp(−x/τ): how a response recovers as the
      delay x grows, for example the response to a pulse given after a
      train.

   region
      In the spontaneous-event detector: neighbouring pixels and frames
      whose :term:`strength` reaches the region threshold (3 × noise in the
      :term:`Standard detector`). Each region is one candidate event.

   response
      The change of the trace from a pulse's :term:`baseline`: the
      :term:`dF/F` in percent for a brightness trace, or the rise above the
      baseline in :term:`percentage points` for a stimulated ÷ unstimulated
      trace.

   response map
      For one pulse, the response of every pixel around its peak, shown as
      an image.

   ring
      The pixels at the same distance, in whole pixels, from the
      :term:`ROI centre`. Ring averages show how the response falls off with
      distance.

   ROI
      Region of interest: the circle in which the evoked response is
      measured. ROI Selection places it at the strongest response; you can
      move it by hand.

   ROI centre
      The centre of the :term:`ROI`. The spatial measures of the evoked
      analysis and the place measures of the spontaneous analysis are
      measured from it.

   ROI file
      ``roi_selections.json``, written by ROI Selection into its output
      folder: the ROI, the electrode mask and the flags of every recording
      folder.

   saturation curve
      top · xⁿ ÷ (halfⁿ + xⁿ), a curve that rises and levels off, for an
      input–output relation such as the response against the current. Also
      called a Hill curve; n, its steepness, is the Hill coefficient.

   SD
      Standard deviation: the usual measure of how widely values spread
      around their mean.

   searched time
      In the spontaneous-event analysis, the part of a recording in which an
      event's start can be counted. It is shorter than the recording.

   sign-flipped
      A control of the spontaneous-event detector: the events it finds in
      the movie turned upside down, that is dimming events, with the same
      rules. Noise gives dimming events as often as brightening ones, but
      dopamine release does not, so their number estimates how many of the
      events are false.

   skip words
      Words that leave a recording out when its file name holds one of them,
      such as ``red`` or ``test``. See :doc:`recordings`.

   slice
      One recording folder: all its recordings are one slice in the tables.

   spatial filter
      In the spontaneous-event detector: a blur that pools each pixel with
      its neighbours, so that events too faint to see in one pixel stand
      out. Its *Pooling width* is the σ of a :term:`Gaussian`: 128 µm in the
      :term:`Standard detector`.

   Standard detector
      The detector built into EMA. It finds events at least 8 times the noise
      after a 128 µm spatial filter and a filter shaped like a dLight event.

   stimulus
      The electrical pulse given through the electrode. Its frame is marked
      by a red dashed line in the Evoked Analysis Configurator.

   strength
      How many times the noise level the filtered signal of a pixel rises,
      in × noise. An event's strength is the largest strength of its
      :term:`region`. For readers who know the term: it is a robust z-score
      of the filtered signal, (value − median) ÷ (1.4826 × median absolute
      deviation), pixel by pixel; 1.4826 × the median absolute deviation
      equals the standard deviation for random noise, but events barely
      change it.

   tau
   τ
      The time constant of an :term:`exponential fit`: the time in which the
      fitted curve falls 63 % of the way to its end level.

   event shape
      The time course the spontaneous-event detector looks for: that of a
      dLight event, with a rise of about 12 ms and a decay of about 200 ms.
      The detector compares it with each pixel's trace, frame by frame:
      where the trace has that shape, the filtered signal rises.
      (Image-analysis specialists call the event shape a template, and the
      two filters together a matched filter.)

   Theil–Sen slope
      The median of the slopes between every pair of points: the slope of a
      straight line that a few outlying points hardly move.

   time between frames
      The time from one frame to the next: 4.849 ms by default. It is a
      setting of each protocol and each detector, used to turn frames into
      ms.

   time-reversed
      A control of the spontaneous-event detector: the events it finds in
      the movie played backwards. A real event (fast rise, slow decay) looks
      wrong backwards and is mostly not found, while noise is found as often
      either way.

   tissue
      In the spontaneous-event detector: the part of the image that is
      searched, made of blocks bright enough to be slice and mostly off the
      electrode.

   trace
      A signal with one value per frame, such as the mean brightness inside
      the ROI.

   unstimulated partner
      The unstimulated recording a stimulated recording is corrected with,
      for bleaching.

   unstimulated recording
      A recording made the same way as a stimulated one, but without the
      stimulus. Its name is ``no`` followed by a number (``no1.tif``).

   window
      A range of frames, given *from* one frame *up to* another; the second
      frame itself is not included.
