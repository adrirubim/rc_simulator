from __future__ import annotations

import ast
from pathlib import Path

UI_ROOT = Path(__file__).resolve().parents[1] / "src" / "rc_simulator" / "ui_qt"

# Strings that are intentionally glyph-only or otherwise language-agnostic.
ALLOWED_LITERALS = {
    "",
    "–",
    "□",
    "✕",
    "+0.000",
}


TARGET_CALL_NAMES = {
    # Common "text surfaces"
    "setText",
    "setToolTip",
    "setPlaceholderText",
    "setWindowTitle",
    # QMessageBox helpers
    "setTextFormat",
    "setInformativeText",
    "setDetailedText",
    "setTextInteractionFlags",
}


TARGET_CTORS = {
    "QLabel",
    "QPushButton",
    "QToolButton",
    "QGroupBox",
    "QDockWidget",
}


def _is_str_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _callee_name(call: ast.Call) -> str | None:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _looks_like_user_visible_text(s: str) -> bool:
    # Skip pure whitespace.
    if not s.strip():
        return False
    # Skip obvious glyph-only strings.
    if s in ALLOWED_LITERALS:
        return False
    # Skip numeric-only.
    if all(ch.isdigit() or ch in ".+- " for ch in s):
        return False
    return True


def test_no_hardcoded_user_visible_strings_in_ui_layer() -> None:
    """
    Audit: user-visible UI text must be sourced from UiStrings / UI proxy,
    not embedded as string literals inside the UI layer.
    """
    offenders: list[str] = []

    for py in sorted(UI_ROOT.rglob("*.py")):
        # Skip __init__.py (usually exports) and anything explicitly internal if needed.
        if py.name == "__init__.py":
            continue

        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            name = _callee_name(node)
            if name is None:
                continue

            # 1) Constructors like QLabel("Text", parent)
            if name in TARGET_CTORS and node.args:
                s = _is_str_constant(node.args[0])
                if s is not None and _looks_like_user_visible_text(s):
                    offenders.append(f"{py.relative_to(UI_ROOT)}:{node.lineno}: ctor {name}({s!r})")
                continue

            # 2) Setter calls like widget.setText("Text")
            if name in TARGET_CALL_NAMES and node.args:
                s = _is_str_constant(node.args[0])
                if s is not None and _looks_like_user_visible_text(s):
                    offenders.append(f"{py.relative_to(UI_ROOT)}:{node.lineno}: call {name}({s!r})")
                continue

    assert not offenders, "Found hardcoded user-visible UI strings:\n" + "\n".join(f"- {o}" for o in offenders)
