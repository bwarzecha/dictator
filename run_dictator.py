#!/usr/bin/env python3
"""Launcher script for Dictator that properly hides from Dock."""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set LSUIElement before importing AppKit/rumps
os.environ['LSUIElement'] = '1'

# Must set this before any GUI imports
import AppKit
bundle = AppKit.NSBundle.mainBundle()
if bundle:
    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
    if info:
        info['LSUIElement'] = '1'

# Now import and run the app
from dictator.main import main

if __name__ == "__main__":
    main()
