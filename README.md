# EMA 3

Analysis of electrically stimulated brain-slice recordings (TIFF movies). EMA 3 is a set of four packages behind
one start window:

| Package | What it does | Status |
|---|---|---|
| **ROI Selection** | Finds the ROI and the electrode of every recording folder, lets you correct them and flag bad recordings | Ready |
| **Evoked Analysis** | Measures the evoked responses inside the selected ROIs with a protocol, and writes the results, labelled from the folder names, in two Excel files laid out for Prism | Ready |
| **Evoked Analysis Configurator** | Makes the protocols the evoked analysis measures with: pulses, windows, comparisons, fits, kinetic and spatial measures, slice summaries | Ready |
| Spontaneous Event Analysis | Finds and measures spontaneous events in unstimulated recordings | Planned |

## Install (once per computer)

1. Install **Python 3.9 or newer** from [python.org](https://www.python.org/downloads/). On Windows, tick
   *Add python.exe to PATH*.
2. In a terminal, go to this folder and install the packages EMA needs:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Optional: put an EMA icon on the Desktop.

   ```bash
   python create_shortcut.py
   ```

## Start

Double-click the Desktop icon or `EMA.pyw`, or run:

```bash
python -m ema
```

## ROI Selection in one minute

1. Choose **ROI Selection** in the start window.
2. Choose the **recordings folder**, check the **settings**, choose an **output folder** (outside the recordings).
   The example on the right shows what the settings find, and follows every change.
3. For each folder in the list: look at the ROI (white circle) and the electrode mask (cyan). Drag the ROI, or
   redraw the electrode with *Edit the electrode* (left button adds, right button removes).
4. Look over the strip of recordings under the plots. Click one to show it; right-click one that fails your
   criteria to flag it.
5. Press **Accept and next**.

Everything is saved as you go in `roi_selections.json` in the output folder. The recordings are only read, never
changed.

## Evoked Analysis Configurator in one minute

1. Choose **Evoked Analysis Configurator** in the start window.
2. Pick a protocol (*2P paired pulse* and *11P pulse train* are built in), or press **New…** to build one from the
   template, and press **Example folder…** to try it on a folder of recordings.
3. Change what you need on the tabs (recordings, pulses and windows, kinetics, spatial, comparisons and summary),
   or drag the windows and fits on the plot. The table under the plot lists every
   measure the analysis will produce, with its value on the example recording.
4. **Save** it under a name of your own. Your protocols are kept in the `protocols` folder of EMA.

## Evoked Analysis in one minute

1. Choose **Evoked Analysis** in the start window.
2. Choose the **ROI file** of ROI Selection (narrow it to one kind of folder, e.g. *Only folders with:
   input output*), a **protocol** and an **output folder**.
3. Check the labels read from the folder names (genotype, treatment, animal, slice, …) on the right, and say what
   each near miss means (e.g. *Contrl* is CTRL). Tick the labels the slices are grouped by.
4. Press **Run the analysis**. `Evoked per recording.xlsx` and `Evoked per slice.xlsx` appear in the output
   folder: a full table, then one sheet per measure laid out to paste into Prism.

A new run measures only new or changed folders and adds them to the files; with another protocol it measures
everything again.

## Documentation

The full documentation, with figures of the procedure and of every setting, is in `docs/`. Build it once with

```bash
python -m pip install -r requirements-dev.txt
```

```bash
python -m sphinx docs docs/_build/html
```

then open `docs/_build/html/index.html`, or press *Documentation* in the start window.

## For developers

```bash
python -m pytest
```

runs the tests (they make their own synthetic recordings). The layout of the code and how to add a setting or a
package are described in `docs/development.rst`. Changes are listed in [CHANGELOG.md](CHANGELOG.md).
