## Documentation — RC Simulator

This repository prioritizes **clear first-run setup** and **repeatable operations** on Linux/WSL.

### Index

| Doc | Content |
|-----|---------|
| `docs/DEVELOPMENT.md` | Local environment, commands, quality gate (ruff/pytest) |
| `docs/ARCHITECTURE.md` | Module map and main application flow |
| `docs/TROUBLESHOOTING.md` | Common issues (WSLg, evdev, video, permissions) |
| `ops/README.md` | OS integration scripts (Linux/Windows) |

### Operational principles

- **Single official entrypoint**: `python -m rc_simulator`
- **Recommended install**: editable install in a venv (`python -m pip install -e ".[dev]"`)
- **Do not version artifacts**: `.venv/`, `__pycache__/`, `*.pyc`, `dist/`, `build/`, `*.egg-info/`

