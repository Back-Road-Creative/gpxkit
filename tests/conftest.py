"""Make the shared synthetic-fixture module importable by name from any test."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
