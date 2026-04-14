from __future__ import annotations

from pathlib import Path


def test_no_egg_info_inside_src_tree() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"

    egg_info = sorted(p for p in src_dir.rglob("*.egg-info") if p.is_dir())
    # setuptools editable installs commonly generate this specific path in-tree
    egg_info = [p for p in egg_info if p.name != "rc_simulator.egg-info"]

    assert not egg_info, "Found generated `*.egg-info` directories under `src/`:\n" + "\n".join(
        f"- {p.relative_to(repo_root)}" for p in egg_info
    )
