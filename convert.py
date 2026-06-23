#!/usr/bin/env python3
"""Thin shim — the CLI now lives in `materials.cli`.

Kept at the repo root so `python convert.py …` and the frozen test fixtures keep
working. The installed console command is `materials-convert` (entry point
`materials.cli:main`); this file is intentionally NOT part of the installed
distribution.
"""
import sys

from materials.cli import main

if __name__ == "__main__":
    sys.exit(main())
