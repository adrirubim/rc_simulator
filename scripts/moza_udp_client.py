#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # Canonical entrypoint (Qt UI) that works from a git checkout too.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from rc_simulator.ui_qt.app import main as run

    run()


if __name__ == "__main__":
    main()
