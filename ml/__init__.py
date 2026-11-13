"""Hazard models for the climate cover: features, model tuning and the payout back-test.

Run everything with:  uv run --group ml python -m ml.run_all
"""

import sys
from pathlib import Path

# The data scripts import each other as top-level modules (`from dgs import ...`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
