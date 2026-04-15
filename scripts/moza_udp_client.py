#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


def main() -> None:
    # Wrapper: avoid importing UI modules and avoid sys.path hacks.
    raise SystemExit(subprocess.call([sys.executable, "-m", "rc_simulator"]))


if __name__ == "__main__":
    main()
