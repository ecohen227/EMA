"""Spontaneous events: the detector, its settings, and the event measures.

Nothing here needs the GUI::

    from ema.recordings import load_stack
    from ema.spontaneous.detection import detect
    from ema.spontaneous.presets import standard_detector
    from ema.spontaneous.measures import measure_events

    detector = standard_detector()
    found = detect(load_stack("no1.tif"), electrode_mask, detector.settings)
    events = measure_events(found, detector.settings, roi_center, electrode_mask)
"""
