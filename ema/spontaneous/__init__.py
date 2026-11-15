"""Spontaneous events: the detector (detector v5 of the metric study), its settings, and the event measures.

Nothing here needs the GUI::

    from ema.recordings import load_stack
    from ema.spontaneous.detection import detect
    from ema.spontaneous.detector import detector_v5
    from ema.spontaneous.measures import measure_events

    detector = detector_v5()
    found = detect(load_stack("no1.tif"), electrode_mask, detector.settings)
    events = measure_events(found, detector.settings, roi_center, electrode_mask)
"""
