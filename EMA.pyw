"""Double-click to start EMA (or run: python -m ema)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ema.app import main

if __name__ == "__main__":  # the analyses' worker processes import this file again; only the first starts EMA
    main()
