# EMA 3

EMA analyses movies of brain slices recorded with a fluorescent sensor such as dLight (TIFF stacks). It measures
**evoked responses** to electrical stimulation and finds **spontaneous events** in unstimulated recordings, and
writes the results in Excel files laid out for GraphPad Prism.

EMA is five packages behind one start window:

- **Evoked responses**: 1 ROI Selection, 2 Evoked Analysis Configurator, 3 Evoked Analysis
- **Spontaneous events**: 1 Spontaneous Event Configurator, 2 Spontaneous Event Analysis

Your recordings are only read, never changed.

## Install (once per computer)

You need two free programs, Python and Git, and then three lines typed in a terminal. It takes about ten minutes.

### 1. Install Python

Download Python from [python.org/downloads](https://www.python.org/downloads/) (the big yellow button) and open
the file you downloaded.

- **Windows:** if the first screen of the installer has a box **Add python.exe to PATH**, tick it, then click
  **Install Now**. The first time you type `py` (step 3), Windows may offer to install Python itself: say yes.
- **Mac:** click **Continue** and **Agree** until it is installed.

Use the Python from python.org, not one from the Microsoft Store or from Homebrew.

### 2. Install Git

Git downloads EMA, and later its updates.

- **Windows:** download **Git for Windows** from [git-scm.com/download/win](https://git-scm.com/download/win)
  (*Click here to download*), open it and click **Next** on every screen, then **Install**. The settings it
  suggests are fine.
- **Mac:** open **Terminal** (see step 3), type `git --version` and press Enter. If Git is missing, the Mac offers
  to install the *command line developer tools*: click **Install**, and wait until it is done.

### 3. Download and install EMA

Open a terminal, a window where you type commands:

- **Windows:** press the Windows key, type `cmd` and press Enter.
- **Mac:** in Finder, open **Applications**, then **Utilities**, then **Terminal**.

Type these three lines, one at a time, pressing Enter after each.

**Windows:**

```
git clone https://github.com/ecohen227/EMA.git
cd EMA
py install.py
```

**Mac:**

```
git clone https://github.com/ecohen227/EMA.git
cd EMA
python3 install.py
```

The first line downloads EMA into a folder called **EMA** in your home folder (`C:\Users\<you>\EMA` on Windows,
`/Users/<you>/EMA` on a Mac). The last line installs the packages EMA needs (a few minutes, with a lot of text
scrolling by), builds the documentation and puts an **EMA** icon on the Desktop. It ends with *EMA is installed*.

## Start

Double-click the **EMA** icon on the Desktop. Without the icon: double-click `EMA.pyw` in the EMA folder.

## Update

When a new version of EMA is out, open a terminal and type, one line at a time (on a Mac, `python3` instead of
`py`):

```
cd EMA
git pull
py install.py
```

Your saved protocols and detectors, your settings and your results are kept.

## If something goes wrong

| The terminal says | What to do |
|---|---|
| `'py' is not recognized` (Windows) or `command not found: python3` (Mac) | Python is not installed: do step 1, then close the terminal, open a new one and try again. |
| `'git' is not recognized` or `command not found: git` | Git is not installed: do step 2, then close the terminal, open a new one and try again. |
| `destination path 'EMA' already exists` | EMA is downloaded already. Type `cd EMA`, then `py install.py` (Mac: `python3 install.py`). |
| `externally-managed-environment` (Mac) | Your `python3` is not the one from python.org. Install Python from python.org (step 1), open a new Terminal and try again. |
| `The packages could not be installed` | Check the internet connection and type the last line again. |
| `Your local changes would be overwritten` (when updating) | A file of EMA itself was changed. Type `git stash`, then `git pull` again. |

**Without Git:** on [github.com/ecohen227/EMA](https://github.com/ecohen227/EMA), click the green **Code** button,
then **Download ZIP**, and unzip it. Open the unzipped folder (the one with `README.md`), click in the address bar
at the top of the window, type `cmd` and press Enter. On a Mac, open Terminal, type `cd ` (with a space), drag the
folder into the Terminal window and press Enter. Then type `py install.py` (Mac: `python3 install.py`). To update,
download the ZIP again.

## Documentation

The documentation explains every package step by step, with figures. Press *Documentation* in the start window,
or open `docs/_build/html/index.html`. Start with *Quick start*: your first analysis with the defaults, nothing to
configure.

The documentation is built by `install.py`. If the *Documentation* button says it has not been built yet, run
`install.py` again (step 3, last line).

## For developers

```bash
python -m pytest
```

runs the tests (they make their own synthetic recordings). The layout of the code is described in
`docs/development.rst`. Changes are listed in [CHANGELOG.md](CHANGELOG.md).
