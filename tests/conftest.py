from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"

for path in (ROOT, SRC, SCRIPTS):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
