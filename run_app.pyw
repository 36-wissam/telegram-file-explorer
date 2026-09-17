"""Windowless launcher for Telegram File Explorer.
Run with pythonw.exe or double-click on Windows to start without a console window.
"""

import os
import sys

# Ensure root directory is on the python search path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import main

if __name__ == "__main__":
    main()
