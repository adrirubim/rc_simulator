# Version Stack

Reference versions for development and CI. Update when upgrading major dependencies.

## Runtime

| Component | Version | Notes |
|-----------|---------|------|
| Python | **3.12** | `pyproject.toml` (`requires-python`) |

## Python dependencies (high level)

| Package | Version | Source |
|--------|---------|--------|
| PySide6 | >= 6.11 | `pyproject.toml` |
| evdev | Linux-only | `pyproject.toml` |
| ruff | >= 0.6 | `pyproject.toml` (dev) |
| pytest | >= 8 | `pyproject.toml` (dev) |

## Local verification (CI parity)

```bash
./scripts/dev-verify.sh
```

