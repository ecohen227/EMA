# Changelog

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
