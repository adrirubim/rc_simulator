#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # Permette esecuzione diretta anche senza PYTHONPATH=src
    repo_dir = Path(__file__).resolve().parent
    repo_root = repo_dir.parent
    src_dir = repo_root / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    # Canonical entrypoint (Qt UI)
    from rc_simulator.ui_qt.app import main as run

    run()


if __name__ == "__main__":
    main()
