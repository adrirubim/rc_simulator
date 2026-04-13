# Contributing to RC Simulator

Thank you for your interest in contributing to this project.  
Please read this guide and the main `README.md` before opening pull requests.

---

## Branching and commits

- Work on **feature branches**; merge changes via pull requests.
- Keep `main` deployable at all times.
- Use short, descriptive branch names: `feat/...`, `fix/...`, `docs/...`.

---

## Local validation (CI parity)

Run the same steps CI runs before opening a pull request.

Single entrypoint (recommended):

```bash
./scripts/dev-verify.sh
```

Equivalent manual commands:

```bash
python3 scripts/audit_layout.py
ruff format --check .
ruff check .
pytest -q
```

---

## Code standards and tests

- Keep imports at the top of the file (avoid inline imports).
- Avoid hardcoded absolute paths like `/home/<user>/...` in runtime; prefer env vars or repo-relative paths when appropriate.
- Add or update tests for new behavior where relevant.

---

## Documentation

- Documentation must be **English**, professional in tone, and aligned with the current project state.
- When behavior changes, update `README.md` and relevant docs under `docs/`.

---

## Pull requests and issues

- Open pull requests against the base branch (usually `main`); CI must be green before merge.
- Clearly describe scope and validation performed.
- When opening an issue, use the **Bug report** or **Feature request** templates.

