## Development

### Requirements

- Python 3.12+
- Linux or WSL (with WSLg for UI)

### Setup (Ubuntu/WSL)

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

### Run

```bash
python -m rc_simulator
```

### Quality (local)

```bash
ruff format .
ruff check .
pytest
```

### Post-move layout audit

```bash
python3 scripts/audit_layout.py
```

### WSL notes

- If the UI doesn't show up, check `DISPLAY` and that WSLg is active (see `docs/TROUBLESHOOTING.md`).
- `evdev` access requires permissions on `/dev/input/*`.

