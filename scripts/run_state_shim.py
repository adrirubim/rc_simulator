from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rc_simulator.core.state import AppPhase, StatusPayload, TelemetryPayload  # noqa: E402

__all__ = ["AppPhase", "StatusPayload", "TelemetryPayload"]
