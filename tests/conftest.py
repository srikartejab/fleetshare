from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON_SRC = ROOT / "packages" / "common" / "src"

if str(COMMON_SRC) not in sys.path:
    sys.path.insert(0, str(COMMON_SRC))
