"""Double-click to start EMA (or run: python -m ema)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ema.app import main

main()
