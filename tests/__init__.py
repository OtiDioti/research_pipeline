"""Test setup for running directly from an uninstalled source checkout."""
import os
from pathlib import Path
import sys


def use_checkout():
    """Use this checkout in tests and in Python CLI subprocesses they launch."""
    source = str(Path(__file__).resolve().parents[1] / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    inherited = os.environ.get("PYTHONPATH", "")
    if source not in inherited.split(os.pathsep):
        os.environ["PYTHONPATH"] = source + (os.pathsep + inherited if inherited else "")
