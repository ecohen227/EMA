# Changelog

## 3.0.0a6 — 2026-11-16: after the first beta test

### Fixed

- ROI Selection's setup window crashed (`'SetupDialog' object has no attribute 'searched_folder'`) when the output
  folder already held selections made with a folder filter.
- The automatic electrode stopped 5 to 7 pixels (80–110 µm) short of the electrode's tip: clearing specks of noise
  also cleared the tip, which is only 1 or 2 pixels wide. The dark pixels joined to the electrode within 15 pixels
  of its end nearest the ROI centre are now given back; nothing else changes (checked on 27 folders). Electrodes
  already saved in ROI files are kept. In the spontaneous analysis, folders without an ROI file entry are searched
  again once (`AUTOMATIC_VERSION` in `roi_selection/detection.py`).
- The spontaneous analysis gave no sign of life while it found the electrode and ROI centre of the folders without
  an ROI file entry: all of them were found before any recording was searched, Stop waited for all of them, and a
  stopped run kept nothing. Folders are now searched in order, a few at a time; the line under the bar names the
  folder whose electrode and centre are being found; **Stop** stops at once and keeps every folder finished.

### Faster

- Recordings are read from disk in one go and then decoded, instead of in about 10,000 small reads per file:
  about 4× faster from a local disk (0.69 → 0.14 s per 56 MB recording on the trial data), and far faster from
  network, cloud or USB drives. The data are identical (checked on 66 recordings). This speeds up every package.
- ROI Selection reads the recordings of the folder on show, and those the next folder opens on, in the
  background; *Detect all folders* reads the next folder while it detects the current one.
- A mean recording is summed as its recordings are read, instead of holding them all in memory.

### Changed for users

- **Not reviewed**: when some folders to measure were not reviewed in ROI Selection, the analyses ask
  **Leave out** (measure only the reviewed folders), **Measure too** (use the automatic ROI and electrode) or
  **Cancel**. Before, *No* measured nothing.
- **Evoked per slice.xlsx is optional**: *Write Evoked per slice.xlsx* in the configurator's *Comparisons and
  summary* tab (`"file"` under `slice_summary` in protocol files). Changing it measures nothing again.
- The default label *Duration* is now *Treatment time*. Labels already saved or remembered keep their names.
- *Also read the folders above the recordings folder* is now *Also read the recordings folder's own name and the
  folders above it*, explained with an example in the documentation.

### Documentation

- The page *Choosing evoked measures* is removed.
- The analysis pages describe the *Not reviewed* question and stopping; the protocol file format lists `file`.

## 3.0.0a5 — 2026-11-15: audit

An audit of the whole program for biologists' use, documentation, code organisation and speed.

### Fixed

- Changing ROI Selection's settings dropped the flags of folders whose ROI and electrode were automatic; folders
  with flags are now kept (`Selections.change_settings`).
- `pyproject.toml` did not list `ema.spontaneous_analysis`, so an installed EMA could not start; packages are now
  found by setuptools.
- A damaged or foreign file in the user's `protocols` or `detectors` folder (not UTF-8, not an object, missing a
  name) stopped the configurators and analyses from opening. Every loader now raises only `OSError` or
  `ValueError`, and the libraries leave such files out.
- An unexpected error while measuring one recording (or a worker process that died) stopped the whole run, and
  the folders measured until then were not saved. It is now noted for that recording on the Notes sheet
  ("Unexpected error (please report it): …"), and a run that stops still saves what it measured, with the details
  of the error in the message.
- An error in a background thread opened the error dialog from that thread, which can crash Qt; it is now only
  written to the console, and the example search of the Spontaneous Event Configurator catches every error.
- A spatial measure computed by a step that did not run was written as an empty column without an error; each step
  now declares its keys (`FOOTPRINT_KEYS`, … in `spatial.py`) and a test checks that every measure belongs to one.
- The Spontaneous Event Configurator saved detectors with problems, had no error handling on Save and Export, asked
  only Discard on unsaved changes, imported without asking about unsaved changes, and could delete the file it
  failed to open. Both configurators now share one library bar (`ema/widgets.py`, `LibraryBar`).
- The plateau fixed in a recovery fit was always 100, also for a ratio (whose full recovery is 1).
- The *Time (ms)* axis at the top of the configurator's trace plot disappeared after the first trace.
- The spontaneous analysis without an ROI file found the electrode and ROI centre of a folder again for every
  recording; it is now found once per folder.
- Leaving a path field of an analysis window without changing it read the path again; for the output folder this
  reloaded the kept analysis and undid label and group changes not yet written. A path is now read only when it
  changes.

### Changed for users

- **Start window:** the packages are grouped under *Evoked responses* and *Spontaneous events*, numbered in the
  order they are used; descriptions wrap instead of being cut off.
- **Plainer words:** the detection score `z` is now *strength* (× noise), in the windows and as the Excel column
  `strength`; *release centre* is now *ROI centre* everywhere (`distance to the ROI centre`, `share near the ROI
  centre`); the built-in detector is called *Standard detector*; the detector's *Template* section is *Event shape*
  and its *Width (σ)* is *Pooling width*; the *Near misses* tab is *Possible typos*; *Time between frames* and
  *Skip recordings with these words* everywhere. Detector files with the earlier measure names still open.
- **Advanced settings:** the detector's expert settings (tissue, bleaching correction, echoes, fit limits, …) are
  in one closed *Advanced* section.
- **Analyses:** the rows are numbered; a question before measuring folders whose ROI was not reviewed in ROI
  Selection, and those folders are marked in the Folders tab; a note when labels or groups changed since the tables
  were written, and a question on closing; a note when the output folder's own labels, filter and groups are taken
  over; "Measure everything again?" names the old and the new protocol or detector. Texts of the spontaneous
  analysis speak of the recordings folder, not the ROI file.
- **Kept results** are measured again only when the protocol or detector changed or EMA computes them differently
  (each analysis's `RESULTS_VERSION`), no longer after every EMA update. Results kept by 3.0.0a4 are measured again
  once.
- **ROI Selection:** *Accept and next* goes to the next folder that is not reviewed yet, and says when all are; a
  legend of the folder marks; *Export table* says where it saved.
- **Labels editor:** Remove, Restore the defaults and Import ask first; a failed export is reported.
- **New protocol form:** shorter texts that fit, the file names the patterns give, and a message instead of a silent
  *Create* when the name is missing.
- **Evoked configurator:** units on the condition range and the fixed plateau; the trace axis is named; the plot
  toolbar keeps only Home, Back, Forward, Pan, Zoom and Save.
- The unexpected-error dialog says what to do, with the details folded away.

### Faster

- The spontaneous detector is about 25 % faster (9.1 s → 6.8 s per recording on one core) and needs a third less
  memory (peak 808 → 540 MB per recording), with results identical to the last digit on 19 recordings of the study: medians taken pixel by
  pixel in memory order (`median_of_rows`), the bleaching correction in chunks, no copy of the movie for the dips,
  and regions labelled by visiting only the pixels above threshold (`connected`, numbered as `ndimage.label`).
  Numba was measured and left out: on top of these changes it would add about 10 % for a new dependency and several
  seconds of compiling in every worker.
- The evoked per-recording workbook no longer re-sorts every slice's recordings for every cell.

### Code

- Shared modules instead of copies: `ema/library.py` (protocol and detector libraries), `ema/kept_results.py` (what
  an analysis keeps and plans), `ema/definitions.py` (one `setting()`, a `Settings` base with checked `from_dict`,
  and `Measure`), `ema/widgets.py` (inputs, settings forms, check lists, the library bar), `ema/paths.py`.
- Matching names on both sides: `evoked/catalogue.py` (was `metrics.py`) and `spontaneous/catalogue.py` (split out of
  `measures.py`) list the measures; `measure_details.py` describes them; `presets.py` holds the built-in protocols
  and detectors and their library, shipped in `built_in/`. `protocol.Measure` is now `Column`;
  `evoked_analysis.window.AnalysisWindow` is `EvokedAnalysisWindow`.
- One list of a protocol's names (`Protocol.names()`); fit results built from the fits' own names; the camera's
  frame time and pixel size in one place (`recordings.FRAME_MS`, `PIXEL_UM`); skip words and the folder filter in
  `recordings.py`.
- Tests for the rules above (`tests/test_structure.py`): the measuring never imports the GUI, every spatial measure
  belongs to a step, every setting can be shown and saved, damaged library files are left out, one failing
  recording does not stop a run. Message boxes a test does not answer now fail the test.
- Worker processes no longer load Qt: `EMA.pyw` and `ema/__main__.py` import the program only in the main process.

### Documentation

- User pages rewritten in plain words without design history; a glossary; *What EMA expects from your
  recordings*; a workflow section; unique page titles; anchors for every measure of the references.
- New developer page *Extending EMA*: how to add a measure, a setting, a protocol feature, a built-in protocol or
  detector, or a package, and the rules of the files.
- A shared copy comes with the documentation already built; the README and the start window say how to build it
  when it is missing.

## 3.0.0a4 — 2026-11-14

### New: Evoked Analysis

- Measures every recording of the folders of an ROI file with a protocol (`ema/evoked/analysis.py`), with each
  folder's ROI and electrode; flagged recordings are left out, and a flagged unstimulated recording is never a
  partner. The values are those the configurator shows on an example recording (a test checks this). A recording's
  condition is the one listed for it, or the number its file name starts with (`Protocol.condition_of`).
- **Kept results.** `evoked_analysis.json` in the output folder keeps the protocol, the labels, the groups and the
  results of every folder (`"format": "EMA evoked analysis"`). A run measures only folders that are new or whose
  fingerprint changed (ROI, electrode, flags, names, sizes and dates of the recordings); other folders keep their
  results; folders that are not in the ROI file are kept or dropped, as the user answers (kept: an analysis can collect several ROI files; dropped: the same recordings moved). With another protocol or EMA version every folder is measured
  again and the files replaced, after asking. A stopped run keeps the folders it finished.
- **Two Excel files** for Prism (`ema/evoked/workbook.py`, new dependency openpyxl): `Evoked per recording.xlsx`
  (one row per recording) and `Evoked per slice.xlsx` (one row per slice), each with the full table, one sheet per
  measure laid out as a Prism grouped table (per recording: a row per condition, a group of columns per group of
  slices, a column per slice, groups padded to the same width) or column table (per slice; or grouped, with a
  label as rows), a *Notes* sheet (what was not measured and why, labels to check) and an *About* sheet (protocol,
  labels, every measure's definition). Empty cells for values that could not be measured. A file open in Excel is
  reported, and *Write the tables* writes both again without measuring.
- **Labels from folder names** (`ema/labels.py`): labels with values and their spellings, and number labels
  (`Slice #`, `F#`); folder names are cut into words, spellings match whole words in order, and the innermost
  folder wins. Disagreeing folder names and names with two values are pointed out. **Near misses** (one or two
  letters off, one word starting the other, or a short form such as CNTRL for control) are listed for the user to
  assign to a value or mark as not a label. Defaults for the lab's folders: Line, Genotype, Treatment, Duration,
  Sex, Animal, Slice. Checked on the 911 recording folders of the study index: every label found except the
  duration of plain `CTRL` folders, no false near misses, and one animal folder filed inside another found.
- **Window** (`ema/evoked_analysis/`): ROI file and folder filter, protocol (library or file), output folder,
  groups; tabs with every folder and its labels (missing and doubtful ones coloured), the label editor (import,
  export, defaults) and the near misses. Runs in a worker thread with progress and *Stop*. Opened from the start
  window.
- After a trial on four animals of the study (25 folders, 131 recordings): the rows of the per-recording Prism
  sheets are the conditions only (a recording without one, such as `test stim 200uA.tif`, is on the Recordings sheet
  only); of two recordings with the same condition the plainest name is shown (`200uA.tif` before
  `200uA test pulse.tif`, `50uA.tif` before `50uA (2).tif`); a recording paired with an unstimulated recording made
  before it (none was made after) gets a note saying how long before. All on the Notes sheet.
- The built-in 2P protocols (and new protocols made from the template) skip recordings with the word *test* in
  their name, as well as *red*: test stimulations such as `test stim 200uA.tif` or `200uA test pulse.tif` are not
  part of the input–output series and no longer count in the slice summaries.
- Simpler window: one short form (ROI file, folders, protocol, output folder, group by, slice sheets) with the
  explanations in tooltips, one-line status texts, the group labels as tick boxes, and one-line hints on the
  Folders, Labels and Near misses tabs; the label editor's buttons are an *Add* menu, *Remove*, ▲ ▼ and a *More*
  menu. The instruction at the top of each Prism sheet is one line.
- The start window lists the Evoked Analysis Configurator before the Evoked Analysis.
- Example output: `docs/make_screenshots.py` runs the analysis on eight made-up slices named like the lab's and
  saves `docs/examples/Example - Evoked per recording.xlsx` and `… per slice.xlsx`; the documentation offers them for
  download and shows excerpts read from them at build time, so the page always matches what EMA writes.
- `ema.evoked.traces.make_movie` builds the pixel movie for the spatial measures.

### New: Spontaneous Event Configurator (the spontaneous-event package split in two)

- The start window has five packages: the spontaneous-event package is split into the **Spontaneous Event
  Configurator** (new) and the **Spontaneous Event Analysis** (still to come), like the evoked ones.
- **Detector v5** of the metric study in `ema/spontaneous/detection.py`: dF/F against a 4th-order polynomial, a
  3-frame running median, the dLight template (12 ms rise, 200 ms decay, 0.1 s before and 0.6 s after the onset) with
  a straight-line baseline, a 128 µm Gaussian over the tissue, the field-wide median removed, a robust z per pixel,
  regions of z ≥ 3 reaching θ 8, the echo rule (ratio 1, 0.53 s, 256 µm) and the 0.32 s end trim; sign-flipped and
  time-reversed controls. The tissue is found in 64 µm blocks from the resting brightness and the ROI file's
  electrode. **Checked against the study:** on the 62 unstimulated recordings of F5819, F5772, M5820 and M5771
  (paired-pulse folders), with the study's centres and electrode masks, the same 55 events at the same frame and
  pixel with the same z, and the same sign-flipped and time-reversed counts in every recording; the study's event
  measures (width, fitted peak, fit quality, centre, local peak, rise, half-decay, distance to the electrode) agree to
  rounding.
- **Every number is a setting** (`ema/spontaneous/settings.py`, 32 settings in 9 groups: movie, tissue, signal,
  template, spatial filter, detection, echoes, controls, measuring), with detector v5's values as defaults; times in
  ms and distances in µm.
- **Measures** (`ema/spontaneous/measures.py`): 21 per event (onset, z; fitted peak, width, full width at half
  maximum, half-maximum area, size, fit quality from a Gaussian fitted to the peak map; local peak, time to peak, rise
  10-90, rise speed, half-width, half-decay, decay tau, area from the pooled trace; x, y, distances to the release
  centre and the electrode, electrode side), 8 per recording (events, searched time, rate, tissue area, density,
  sign-flipped, time-reversed, pixel noise) and 16 per slice (counts, rates and the controls; share near the release
  centre and on the electrode side; nearest-neighbour distance, clustering index, recurring sites; share together;
  release per minute), plus per-slice summaries (median, mean, min, max) of any event measure. Each is described in
  full in `ema/spontaneous/measure_details.py`; a test requires it.
- **Detectors** are saved as JSON (`"format": "EMA spontaneous detector"`) in a library: one built in, *Detector v5*
  (the 128 µm filter the study found best), in `ema/spontaneous/presets`; the user's in `detectors/`.
- **Window** (`ema/spontaneous_configurator/`): the detector in three tabs (settings in sections built from the
  settings list; event measures; recording and slice measures), tried on an example folder's unstimulated recordings
  in a worker thread: each pixel's largest z with the events circled, the selected event's peak map with its
  half-maximum circle and its pooled trace, and the table of its measures.
- Documentation: *Spontaneous Event Configurator* pages (how the detector works, the configurator, every setting,
  the measure reference, choosing measures with the study's values, the detector file), with figures made by
  `docs/make_spontaneous_figures.py` from the sample unstimulated recording with two events planted in it.

### New: Spontaneous Event Analysis

- Searches the unstimulated recordings of every folder under a **recordings folder** with a detector
  (`ema/spontaneous/analysis.py`, `Recordings`); the ROI file is optional. A folder it covers uses its reviewed
  electrode, release centre and flags; any other folder's are found automatically from its stimulated recordings, as in
  ROI Selection; a folder without stimulated recordings is searched without an electrode and its place measures are
  empty. The *Electrode and centre* column says which. Recordings with a skip word are left out.
  Recordings are searched in parallel, one process per core but one (at most 8), each limited to one thread: about
  3 s per recording on a 12-core laptop, against 9 s one at a time.
- **Kept results** in `spontaneous_analysis.json` (`"format": "EMA spontaneous analysis"`): the detector, labels, groups,
  and every recording's and event's measures. A run searches only new or changed folders (fingerprints of the ROI file
  entry and the recordings); other settings or skip words search everything again, after asking; a change
  of the reported measures only rewrites the tables, since every measure is kept.
- **Two Excel files** (`ema/spontaneous/workbook.py`): `Spontaneous per event.xlsx` (Events, Recordings, one Prism
  column table per event measure with every event of each group) and `Spontaneous per slice.xlsx` (Slices with the
  summaries of event measures, one Prism column or grouped table per slice measure), each with Notes and About.
- **Checked on real recordings:** on the 25 paired-pulse folders of F5819, F5772, M5820 and M5771, with an ROI file
  from ROI Selection's automatic detection, the same event count as the study's detector v5 in all 62 recordings the
  study had searched; 137 events in all 151 unstimulated recordings (8.0 per minute, 2 sign-flipped, 1 time-reversed).
- **One window for both analyses** (`ema/analysis_window.py`): the Evoked Analysis window, made general; each
  analysis brings its title, protocol or detector library, files, and run and write functions (a `Kind`); the
  spontaneous one also a recordings folder, with the ROI file optional. The label
  editor moved to `ema/labels_editor.py`; what both analyses' Excel files share moved to `ema/excel.py`. The labels last
  used are remembered for both (`folder_labels`).
- `ema/__main__.py` and `EMA.pyw` start EMA only when run themselves, not when a worker process imports them.
- Documentation: *Spontaneous Event Analysis* pages, with example files made by `docs/make_screenshots.py` from four
  made-up slices (the sample unstimulated recording with planted events).

### Removed: OneDrive handling

- EMA assumes every recording is on the computer. `ema.recordings.is_online_only` is gone, and with it the
  question before downloading online-only recordings in ROI Selection, the online-only messages of its setup
  example, and the online-only checks of the configurator's example folder.

### New: the Evoked Analysis Configurator

- Makes, checks and saves **protocols**: the trace to measure (ROI brightness, or stimulated ÷ unstimulated in %),
  how each stimulated recording finds its unstimulated partner, which recordings, the baseline and peak window of
  every pulse, comparisons, exponential fits, kinetic and spatial measures, slice summaries and fits across
  conditions. Saved as JSON (`"format": "EMA evoked protocol"`) in a library: built-in
  protocols in `ema/evoked/presets`, the user's in `protocols/` of the program folder.
- **One template** for every protocol (`ema/evoked/template.py`): a train of pulses (first stimulus, number,
  interval, window lengths, own or shared baselines) and an optional recovery pulse at a list of delays, counted
  from the end of the train or from its last pulse. *New…* opens it as a form, with *Fill in like 2P / 11P*.
- Tried live on an example folder (ROI and electrode found automatically or taken from an ROI Selection file):
  windows, stimuli, baselines, peaks and fits drawn on the trace; windows, fits and stimuli can be dragged; every
  measure the analysis will produce is listed with its value on the example and its definition.
- **Fits** are drawn as purple bands in the middle third of the plot, with the fitted curve and τ on them, and can
  be dragged. A fit can be single or **double** exponential (τ fast, τ slow, fast fraction).
- **Kinetics** tab: time to peak, onset, rise 10–90 and 20–80, max rise slope, half-width, half-decay, 1/e decay,
  max decay slope, area and signal-to-noise, on chosen pulses, with *All* / *None*.
- **Spatial** tab: footprint width λ, footprint half-width, r50, tail fraction, centroid offset, elongation,
  heterogeneity, hot spots, release latency slope and far-near delay on chosen pulses, and near-to-far indices of
  chosen comparisons, with the settings of the maps and rings. The plot shows the response map (or half-rise
  latency map) with its bands and centroid, and the ring profile with the footprint fit.
- **Decay with distance** (Spatial tab): the response map followed from the peak on in bins as long as the map,
  up to the next stimulus, the end of the recording or *Follow the decay for at most* (`follow_ms`, 1500 ms).
  Measures: *far-near decay ratio* (half-decay time of the far band ÷ that of the near band) and *decay-distance
  slope* (Theil–Sen slope of each ring's half-decay time against its distance, ms/mm). *Show: Decay with distance*
  draws the two bands against time. The footprint width is measured at the peak only: widths fitted to every bin
  (with the measures *width ratio at half decay* and *contraction rate*) were tried and dropped as too noisy.
- **Fits across conditions** (last tab): a recovery curve, plateau − (plateau − start)·exp(−x/τ), with the plateau
  fitted or fixed (e.g. P11/P1 against the delay, fixed at 100 %), or a saturation (Hill) curve,
  top·xⁿ ÷ (halfⁿ + xⁿ) (e.g. the response against the current: the half-max current). Fitted per slice; kept only
  with more recordings than free parameters and a result inside set bounds.
- **Unstimulated partners for every protocol.** By default each stimulated recording is paired with the
  unstimulated recording (`no<n>…`) made right after it, found from the TIFF time stamps (DateTime tag), or the
  one made right before it if none was made after. A listed recording can name another partner; partners can also
  be named for every listed recording (`"as listed"`), or not used (`"none"`). With a brightness trace the partner
  corrects bleaching: stimulated × mean(partner over the first baseline window) ÷ partner, which keeps brightness
  units and dF/F; maps are corrected pixel by pixel. New protocol entry `recordings.unstimulated_partner`; a file
  without it is read as before (`"as listed"` for a ratio trace, `"none"` for brightness). A stimulated ÷
  unstimulated trace no longer needs a list of recordings. `ema/evoked/traces.py` makes the trace;
  `ema.recordings.acquisition_time` and `recorded_after` find the partner.
- Built-in protocols: *2P paired pulse* now corrects with the unstimulated recording made right after each
  recording (the standard procedure from now on); the new *2P paired pulse, uncorrected* measures as recorded, for
  slices without unstimulated recordings; *11P pulse train* names its partners as before.
- The kinetic and spatial measures are one catalogue (`ema/evoked/metrics.py`), from which the tabs, the measure
  list and the documentation tables are built, so new measures can be added in one place. Each is described in
  full (formula, method, when it is empty, what it reflects, caveats) in `ema/evoked/metric_details.py`, from
  which the documentation's measure reference page is built; a test requires an entry for every measure.
- Documentation: new pages *Measure reference* and *Choosing measures* (with the literature behind them), the
  trace and partner rules, decay with distance, and fits across conditions. The measure reference describes every
  measure a protocol can produce (baselines, peaks, responses, comparisons, fits, kinetic and spatial measures,
  near-to-far indices, slice summaries, fits across conditions) the same way: how it is named, unit, definition,
  formula, method, when it is empty, what it reflects, caveats and a worked example whose numbers are checked by
  the tests; plus how measures are named and what each unit means. Built from `ema/evoked/metric_details.py`.
- Fixed: switching protocols while the Spatial tab was open raised "'NoneType' object has no attribute
  'get_position'" and then a KeyError on the colour bar. The colour bar now has an area of its own that is
  redrawn in place.
- *Place pulses…* builds a regular train in an existing protocol.
- Any window or pulse can be timed **per recording** in a list of recordings, which is how the recovery pulse
  of the 11P protocol is described. With *Per-recording windows follow the condition*, changing a recording's
  delay moves its windows by as much.
- `ema/evoked/measures.py` measures one trace with a protocol and summarises a slice; `ema/evoked/spatial.py`
  measures a movie.
- `Blitter` moved from `ema/roi_selection/plots.py` to `ema/blit.py`, to be shared.

### The spatial measures compared with the metric study

The definitions follow the study's `footprint.py`, `maps_5cur.py`, `vein_stats.py` and `latency_batch.py`, with
three differences:

- The footprint fit and the half-width use each ring's mean distance from the centre (about k + 0.5 pixels for
  ring k); the study used k. On a synthetic Lorentzian of λ = 300 µm the study's convention gives about 294 µm,
  this one 300 µm.
- Response maps are made from the raw frames relative to the pulse's own baseline window, blurred once
  (σ 1 px by default); the study smoothed every frame of a dF/F movie relative to frames 10–95.
- The near-to-far bands are settings (near 0–160 µm, far 400–640 µm by default, as in `vein_stats.py`).

On the sample slice (300 µA) the release-latency slope is 9.3 ms/mm; the study's pilot reported 18.6 ms/mm on
average. Not compared on more slices.

### The built-in protocols reproduce EMMA 2P v1.0 and 11P v1.1

`tests/test_evoked_measures.py` checks on synthetic traces that every value equals, bit for bit, the value of
the earlier programs' formulas (taken from EMA 2.4's `analysis.py`, which matched EMMA byte for byte). For 2P this
is *2P paired pulse, uncorrected*; *2P paired pulse* applies the same formulas to the corrected trace, whose
correction is checked against EMA 2.4's `divide_background` and whose pairing follows its `background_pairs`
(except that a recording without a time stamp gets no partner instead of the mean of every unstimulated one):

| EMMA column | Measure with the built-in protocol |
|---|---|
| 2P `B1`, `P1`, `B2`, `P2` | `B1`, `P1`, `B2`, `P2` |
| 2P `P1 dF/F (%)`, `P2 dF/F (%)` | `P1 response`, `P2 response` (brightness trace: P ÷ B × 100 − 100) |
| 2P `PPR` | `PPR` (comparison P2 ÷ P1, as a ratio) |
| 2P `Tau (ms)` | `Tau` (fit 4 frames after the maximum of P1, 412 frames) |
| 2P aggregated `<x>_min`, `_max`, `_mean`, `_mean_100_400` | `<x> min`, `<x> max`, `<x> mean`, `<x> mean 100-400` |
| 2P aggregated `B1_max_abs_diff`, `B2_max_abs_diff` | `B1 spread`, `B2 spread` |
| 11P `BL`, `P1` … `P10`, `BLPre11`, `P11` | the same names (stimulated ÷ unstimulated trace) |
| 11P `P1/BL` … `P10/BL`, `P11/BLPre11` | `P1 response` … `P11 response` (P − baseline) |
| 11P `P2/P1`, `P10/P1`, `P11/P1`, `P11/P10` | the same names (comparisons in percent) |
| 11P `nP1/BL` … `nP10/BL` | the same names (comparisons with P1, as ratios) |

Not carried over, because they are not measures of a protocol: the ROI position, the current, the delay and the
recording name columns (the analysis will write them), and EMMA's rounding of the 2P tables to 2 decimals.
The stimulus frames of the built-in protocols (P1 at frame 103, the 11P recovery pulses at 412, 515, 825 and
1340, each delay counted from the end of the train) are worked out from the protocol timing; they only affect the
new kinetic measures.

## 3.0.0a3 — 2026-11-14

- **Setup dialog:** the settings sections (*ROI*, *Timing*, *Electrode*, *Display*) are closed by default and
  open when their heading is clicked. The defaults are meant to stay as they are, so they no longer fill the
  dialog. The heading of a closed section says how many of its settings are not at their default.

## 3.0.0a2 — 2026-11-14

ROI Selection, after the first round of use.

### New

- **Strip of all recordings.** Under the plots, one card per recording shows its response map with the ROI, its
  ROI trace and the peak of the trace, all on shared scales. Click a card to show the recording; right-click it
  to flag or unflag it. Cards fill one at a time while the recordings are read, so the window stays usable.
- **Mean recording.** The recordings that set the ROI are averaged into one mean recording. It is the first entry
  of the *Recording* list and the first card of the strip, and a folder opens on it. It cannot be flagged.
- **The frame slider is always there.** It starts at the peak. *Response (dF/F)* now follows the slider too, so
  the response can be watched rising and fading. It rests while the baseline image is on show.
- **Live example in the setup dialog.** The right half of the dialog runs the detection on one recording folder
  and redraws after every change to a setting. *Settings…* starts it on the open folder.
- The trace plot marks the frames averaged at the peak.
- **Folder filter.** Step 1 of the setup dialog has *Only folders with* and *Skip folders with*: words that the
  path of a recording folder must or must not contain. Only folders that pass are listed, offered as examples and
  saved. The filter is saved in the ROI file as `folder_filter`; files without it load with no filter. Changing
  the filter undoes no review; saved folders that no longer pass are removed after a question.

### Changed

- **Automatic ROI:** the recordings are averaged first and one response map is made from the mean recording.
  Before, one response map was made per recording and the maps were averaged. On the synthetic test recordings
  both give the same centre and maps that differ by less than 0.0003 dF/F. A folder with one such recording is
  not affected at all.
- **Show:** *Mean response* left this list (it is the mean recording now), and *Movie* is called *Brightness*.
- **Flag all in this folder…** asks for the reason in a small dialog instead of taking it from the reason box.
- **Settings dialog:** the other electrode settings are greyed out while *Find the electrode automatically* is
  off. *Display* moved to the right column so the dialog fits a small screen.
- **After a settings change every folder has to be reviewed again.** Before, folders adjusted by hand kept their
  review. What was set by hand is still kept; what was found automatically in such a folder (for example its
  electrode mask) is now found again with the new settings, where it used to stay as it was. Until then the
  folder's `automatic_roi` is `null` in the ROI file. The setup dialog asks before reviews are lost.
- Up to 24 recordings stay in memory (about 1.3 GB at the standard size), so that the strip can follow the ROI
  without reading the files again. It was 4.
- Fixed: the electrode settings were not greyed out when the dialog opened with *Find the electrode
  automatically* already off.
- The documentation no longer compares EMA 3 with earlier versions. Those notes are in this file only.

## 3.0.0a1 — 2026-11-14

EMA 3 is a new program beside EMA 2.4, not an edit of it. It will hold four packages behind one start window. This
first version has the start window and the first package, ROI Selection. Nothing here writes the historical 2P and
11P tables, so the byte-identical rule of EMA 2 is not touched yet.

### New

- **Start window** (`ema/launcher.py`) listing ROI Selection, Evoked Analysis, Evoked Analysis Configurator and
  Spontaneous Event Analysis. Only ROI Selection can be opened.
- **ROI Selection** (`ema/roi_selection/`):
  - a setup dialog for the recordings folder, the settings and the output folder;
  - every folder under the recordings folder that holds TIFF movies is listed, with a drop-down list of its
    recordings, an image (response map, mean response map, baseline image or movie) and the ROI trace;
  - the ROI and the electrode mask are found automatically per folder and can be changed by hand: drag the ROI,
    outline areas to add to or remove from the electrode mask;
  - recordings can be flagged, with a reason;
  - folders are marked as reviewed with *Accept and next*;
  - everything is saved after every change in `roi_selections.json` in the output folder; a table for Excel can be
    exported.
- **Sphinx documentation** in `docs/`, with figures of the procedure and of every setting drawn by the program's
  own functions (`docs/make_figures.py`) and screenshots taken from the program (`docs/make_screenshots.py`).
- **Tests** (`tests/`, 34) on synthetic recordings with a known release centre and electrode.

### Kept from earlier versions

- The first frame of every TIFF is dropped, so frame numbers mean the same as in EMA 2.
- The ROI is a disk of radius 20 pixels by default; a pixel is inside when its distance to the centre is at most
  the radius.
- The ROI trace shown uses the whole disk, electrode pixels included, as in EMA 2.
- The electrode mask follows `emask.py` of the metric study: same threshold (0.90), surroundings (31 px median),
  size, length and distance rules, and 1 px growth.
- Recordings are read-only. The output folder must be outside the recordings folder. Online-only (OneDrive) files
  are downloaded only after the user agrees.
- The error dialog for unexpected errors, the splash screen, the taskbar icon and `create_shortcut.py`.

### Different from earlier versions

- **Automatic ROI:** the metric study took the maximum of the smoothed mean of the 300 and 400 µA peak dF/F maps.
  EMA 3 does the same on 200 and 300 µA by default (a setting), and builds each map in fewer steps: the raw frames
  around the peak are averaged and divided by the baseline, and the mean map is smoothed once (sigma 2 px). The
  study smoothed every frame first (3 frames, sigma 1 px). On the two sample recordings the centres differ by at
  most one pixel. Not checked on the full study.
- **Folders without the named recordings** (11P folders) use every stimulated recording, not `hi1` alone.
- **ROI positions are whole pixels** in every protocol. EMA 2 snapped 2P clicks to whole pixels and kept sub-pixel
  positions for 11P (HANDOFF §5).
- **The ROI radius is saved** with every folder, and is a setting (HANDOFF §5: it was not written anywhere).
- **Electrode mask at the image edge:** gaps are closed on a padded image, so the mask now includes the outermost
  pixel column. In `emask.py` the closing removed it.
- **No pandas dependency.**

### Decisions still open

- Whether the later analysis leaves the electrode pixels out of the ROI. ROI Selection saves both masks and does
  not decide.
- The automatic detection was tried on the two sample slices only. The defaults of the electrode mask were tuned on
  48 slices in the metric study; the simplified ROI detection has not been compared with the study on more data.
