# Technical Guide — RC Simulator

Single “flat” technical guide for this repository.
If this guide disagrees with the code, **the code wins**.

## Table of Contents

- [Architecture](#architecture)
- [Operations](#operations)
- [Security](#security)
- [Key Files](#key-files)

## Architecture

See also `docs/ARCHITECTURE.md`.

## Operations

- Linux ops: `ops/linux/`
- Windows ops: `ops/windows/`

## Security

See `SECURITY.md` (reporting + guidelines).

## Key Files

- Entrypoint: `src/rc_simulator/__main__.py`
- Config: `src/rc_simulator/core/config.py`
- UI: `src/rc_simulator/ui_qt/`
- Services: `src/rc_simulator/services/`

