#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    severity: str  # "INFO" | "WARN" | "ERROR"
    title: str
    details: str


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except Exception:
        return str(p)


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def audit(repo_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    ignored_dirnames = {".venv", ".git", ".pytest_cache", ".ruff_cache", "__pycache__"}
    self_path = Path(__file__).resolve()

    legacy_dir = repo_dir / "src" / "rc_simulator_frontend"
    if legacy_dir.exists():
        findings.append(
            Finding(
                "WARN",
                "Legacy folder still present",
                "Found `src/rc_simulator_frontend/`. If you already decided to keep `rc_simulator`, delete it.\n"
                f"- {_rel(legacy_dir, repo_dir)}",
            )
        )

    pyproject = repo_dir / "pyproject.toml"
    if not pyproject.exists():
        findings.append(
            Finding(
                "ERROR",
                "Missing pyproject.toml",
                "No `pyproject.toml` found at the repository root. If you moved folders, verify the repo root.",
            )
        )

    egg_info_candidates = list(repo_dir.glob("src/*.egg-info")) + list(repo_dir.glob("src/**/*.egg-info"))
    egg_info = sorted({p.resolve() for p in egg_info_candidates})
    if egg_info:
        findings.append(
            Finding(
                "WARN",
                "Build artifacts inside src/",
                "Found generated `*.egg-info` directories inside the project tree:\n"
                + "\n".join(f"- {_rel(p, repo_dir)}" for p in egg_info),
            )
        )

    # Common duplicates: ops/linux/*.sh copied to repo root
    ops_linux = repo_dir / "ops" / "linux"
    if ops_linux.exists():
        for sh in ops_linux.glob("*.sh"):
            root_copy = repo_dir / sh.name
            if root_copy.exists():
                same = False
                try:
                    same = _read_text(root_copy) == _read_text(sh)
                except Exception:
                    same = False
                content_note = (
                    "The content is identical." if same else "The content differs; keep a single source of truth."
                )
                findings.append(
                    Finding(
                        "INFO" if same else "WARN",
                        f"Duplicate script: {sh.name}",
                        "Found in two locations:\n"
                        f"- {_rel(sh, repo_dir)}\n"
                        f"- {_rel(root_copy, repo_dir)}\n" + content_note,
                    )
                )

    # Root shims that touch sys.path to point at src/
    shim_candidates = [
        repo_dir / n
        for n in (
            "services.py",
            "state.py",
            "ui_theme.py",
            "ui_widgets.py",
            "moza_udp_client.py",
        )
    ]
    shim_re = re.compile(r"sys\.path\.insert\(0,\s*str\(_SRC\)\)")
    for p in shim_candidates:
        if not p.exists():
            continue
        text = _read_text(p)
        if shim_re.search(text):
            findings.append(
                Finding(
                    "INFO",
                    f"Root shim: {p.name}",
                    "This file modifies `sys.path` to import from `src/` without installing the package. "
                    "This is usually a migration/compatibility signal; prefer proper installs when possible.",
                )
            )

    # Absolute /home/... paths in code and scripts
    abs_hits: list[str] = []
    for p in repo_dir.rglob("*"):
        if any(part in ignored_dirnames for part in p.parts):
            continue
        if not p.is_file():
            continue
        if p.resolve() == self_path:
            continue
        if p.suffix.lower() not in {".py", ".sh", ".md", ".txt"}:
            continue
        text = _read_text(p)
        for m in re.finditer(r"/home/[^\s\"']+", text):
            abs_hits.append(f"{_rel(p, repo_dir)}: {m.group(0)}")
            if len(abs_hits) >= 50:
                break
        if len(abs_hits) >= 50:
            break
    if abs_hits:
        findings.append(
            Finding(
                "WARN",
                "Absolute path references (/home/...)",
                "These paths usually break if you moved the project or changed user/host.\n"
                + "\n".join(f"- {h}" for h in abs_hits),
            )
        )

    return findings


def main() -> int:
    repo_dir = Path(__file__).resolve().parents[1]
    findings = audit(repo_dir)
    if not findings:
        print("OK: no typical post-move mixing signals detected.")
        return 0

    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings = sorted(findings, key=lambda f: (order.get(f.severity, 9), f.title))

    for f in findings:
        print(f"[{f.severity}] {f.title}")
        print(f.details.rstrip())
        print()

    has_error = any(f.severity == "ERROR" for f in findings)
    return 2 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
