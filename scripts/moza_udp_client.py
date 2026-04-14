#!/usr/bin/env python3
from __future__ import annotations


def main() -> None:
    # Canonical entrypoint (Qt UI). This script assumes the package is installed in the active environment.
    from rc_simulator.ui_qt.app import main as run

    run()


if __name__ == "__main__":
    main()
