from __future__ import annotations

from pathlib import Path


def test_ui_qt_does_not_import_services_or_adapters() -> None:
    """
    Guardrail: UI must not depend on IO layers.

    UI may depend on `core/`, `ports/`, and `app/` (controller), but not `services/` or `adapters/`.
    """

    repo_root = Path(__file__).resolve().parents[1]
    ui_root = repo_root / "src" / "rc_simulator" / "ui_qt"

    forbidden_snippets = (
        "rc_simulator.services",
        "rc_simulator.adapters",
        "from ...services",
        "from ..services",
        "from ...adapters",
        "from ..adapters",
        "import rc_simulator.services",
        "import rc_simulator.adapters",
        # Also forbid direct IO libs in UI (keep it pure Qt rendering).
        "import socket",
        "from socket",
        "import evdev",
        "from evdev",
        "import gi",
        "from gi",
    )

    offenders: list[str] = []
    for path in ui_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for snip in forbidden_snippets:
            if snip in text:
                offenders.append(f"{path}: contains `{snip}`")
                break

    assert not offenders, "UI layer imports forbidden modules:\n" + "\n".join(offenders)
