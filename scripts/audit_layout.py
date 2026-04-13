#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


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
                "Carpeta legacy todavía presente",
                "Existe `src/rc_simulator_frontend/`. Si ya decidiste quedarte con `rc_simulator`, puedes borrarla.\n"
                f"- { _rel(legacy_dir, repo_dir) }",
            )
        )

    pyproject = repo_dir / "pyproject.toml"
    if not pyproject.exists():
        findings.append(
            Finding(
                "ERROR",
                "Falta pyproject.toml",
                "No se encontró `pyproject.toml` en la raíz. Si moviste carpetas, revisa el root del repo.",
            )
        )

    egg_info = sorted({p.resolve() for p in (list(repo_dir.glob("src/*.egg-info")) + list(repo_dir.glob("src/**/*.egg-info")))})
    if egg_info:
        findings.append(
            Finding(
                "WARN",
                "Artefactos de build dentro de src/",
                "Se encontraron directorios `*.egg-info` (generados) dentro del árbol del proyecto:\n"
                + "\n".join(f"- {_rel(p, repo_dir)}" for p in egg_info),
            )
        )

    # Duplicados típicos: ops/linux/*.sh copiados en raíz
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
                findings.append(
                    Finding(
                        "INFO" if same else "WARN",
                        f"Duplicado de script: {sh.name}",
                        "Existe en dos ubicaciones:\n"
                        f"- {_rel(sh, repo_dir)}\n"
                        f"- {_rel(root_copy, repo_dir)}\n"
                        + ("El contenido es idéntico." if same else "El contenido difiere; conviene dejar una sola fuente de verdad."),
                    )
                )

    # Shims en raíz que tocan sys.path para apuntar a src/
    shim_candidates = [repo_dir / n for n in ("services.py", "state.py", "ui_theme.py", "ui_widgets.py", "moza_udp_client.py")]
    shim_re = re.compile(r"sys\.path\.insert\(0,\s*str\(_SRC\)\)")
    for p in shim_candidates:
        if not p.exists():
            continue
        text = _read_text(p)
        if shim_re.search(text):
            findings.append(
                Finding(
                    "INFO",
                    f"Shim en raíz: {p.name}",
                    "Este archivo modifica `sys.path` para poder importar desde `src/` sin instalar el paquete. "
                    "No es necesariamente malo, pero suele ser señal de compat/migración.",
                )
            )

    # Rutas absolutas /home/... en código y scripts
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
                "Referencias a rutas absolutas (/home/...)",
                "Estas rutas suelen romperse si moviste el proyecto o cambiaste de usuario/host.\n"
                + "\n".join(f"- {h}" for h in abs_hits),
            )
        )

    return findings


def main() -> int:
    repo_dir = Path(__file__).resolve().parents[1]
    findings = audit(repo_dir)
    if not findings:
        print("OK: no se detectaron señales típicas de mezcla.")
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

