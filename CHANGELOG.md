# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-16

### Added

- Native Windows build system via PyInstaller (`rc-simulator.spec` + `scripts/build-win.bat`).
- Windows executable icon sync: `.ico` is available under `src/rc_simulator/resources/icons/` for bundling.

### Changed

- Release seal: repository version bumped to `1.0.0` (Gold Master).

## [0.1.0] - 2026-04-13

### Added

- First public documentation baseline (`docs/` index + development/architecture/troubleshooting).
- Layout audit script (`scripts/audit_layout.py`) to detect post-move mixing.

### Changed

- Cleaned legacy frontend remnants and normalized repo layout (ops scripts under `ops/`).

