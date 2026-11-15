# EMA 3

Analysis of electrically stimulated brain-slice recordings (TIFF movies). EMA 3 is a set of four packages behind
one start window:

| Package | What it does | Status |
|---|---|---|
| **ROI Selection** | Finds the ROI and the electrode of every recording folder, lets you correct them and flag bad recordings | Ready |
| Evoked Analysis | Measures the evoked responses inside the selected ROIs | Planned |
| Evoked Analysis Configurator | Sets the windows, fits and comparisons of the evoked analysis | Planned |
| Spontaneous Event Analysis | Finds and measures spontaneous events in unstimulated recordings | Planned |

EMA 2.4 (`EMA_V2` in the handoff) stays the program for the evoked analysis until that package is built here.

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
3. For each folder in the list: look at the ROI (white circle) and the electrode mask (cyan). Drag the ROI, or
   redraw the electrode with *Edit the electrode* (left button adds, right button removes). Tick *Flag this
   recording* for recordings that fail your criteria.
4. Press **Accept and next**.

Everything is saved as you go in `roi_selections.json` in the output folder. The recordings are only read, never
changed.

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
