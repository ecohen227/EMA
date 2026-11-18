"""Install EMA, or bring an updated EMA up to date: the packages it needs, its documentation and a Desktop icon.

    Windows:  py install.py
    Mac:      python3 install.py

Run it in the EMA folder (the one with README.md). It needs an internet connection the first time. Running it again
is safe: it only adds what is missing. Add --no-shortcut to leave the Desktop alone.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args):
    """Run this same Python with these arguments in the EMA folder. True if it worked."""
    return subprocess.run([sys.executable, *args], cwd=ROOT).returncode == 0


def main():
    if sys.version_info < (3, 9):
        sys.exit(f"EMA needs Python 3.9 or newer, and this is Python {sys.version.split()[0]}.\n"
                 "Install the newest Python from https://www.python.org/downloads/ and run this again.")
    shortcut = "--no-shortcut" not in sys.argv
    steps = 3 if shortcut else 2

    print(f"\n[1/{steps}] Installing the packages EMA needs. The first time this takes a few minutes.\n", flush=True)
    if not run("-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements-dev.txt"):
        sys.exit("\nThe packages could not be installed (see the message just above). Check the internet connection "
                 "and run this again.")

    print(f"\n[2/{steps}] Building the documentation.\n", flush=True)
    if not run("-m", "sphinx", "-q", "docs", str(Path("docs") / "_build" / "html")):
        print("\nThe documentation could not be built (see the message above). EMA works without it; run this again "
              "later to try once more.")

    icon = shortcut
    if shortcut:
        print(f"\n[3/{steps}] Putting an EMA icon on the Desktop.\n", flush=True)
        icon = run("create_shortcut.py")
        if not icon:
            print("\nThe Desktop icon could not be made.")

    where = "the EMA icon on the Desktop" if icon else f"EMA.pyw in {ROOT}"
    print(f"\nEMA is installed. To start it, double-click {where}.")


if __name__ == "__main__":
    main()
