# EMA 3

EMA analyses movies of brain slices recorded with a fluorescent sensor such as dLight (TIFF stacks). It measures
**evoked responses** to electrical stimulation and finds **spontaneous events** in unstimulated recordings, and
writes the results in Excel files laid out for GraphPad Prism.

EMA is five packages behind one start window:

- **Evoked responses**: 1 ROI Selection, 2 Evoked Analysis Configurator, 3 Evoked Analysis
- **Spontaneous events**: 1 Spontaneous Event Configurator, 2 Spontaneous Event Analysis

Your recordings are only read, never changed.

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

## Documentation

The documentation explains every package step by step, with figures. Press *Documentation* in the start window,
or open `docs/_build/html/index.html`. Start with *Getting started* and *What EMA expects from your recordings*.

If the `docs/_build` folder is missing, build the documentation once:

```bash
python -m pip install -r requirements-dev.txt
python -m sphinx docs docs/_build/html
```

## For developers

```bash
python -m pytest
```

runs the tests (they make their own synthetic recordings). The layout of the code is described in
`docs/development.rst`. Changes are listed in [CHANGELOG.md](CHANGELOG.md).
