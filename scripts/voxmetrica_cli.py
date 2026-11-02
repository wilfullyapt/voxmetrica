#!/usr/bin/env python3
"""Backward-compatible CLI entry — prefer `voxmetrica` console script. """
from voxmetrica.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
