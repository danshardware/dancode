"""Integration tests for engine/paths.py.

IMPORTANT: engine.paths freezes DATA_DIR at import time from COUNCIL_DATA_DIR.
The council_data_dir fixture (conftest.py) sets the env var and reloads the
module so each test sees an isolated DATA_DIR.
"""

from __future__ import annotations

import importlib


def test_data_dir_set_before_import(council_data_dir):
    """DATA_DIR should equal the value of COUNCIL_DATA_DIR after reload."""
    import engine.paths as paths_mod
    assert paths_mod.DATA_DIR == council_data_dir


def test_resolve_prefers_data_dir(council_data_dir):
    """resolve() returns the DATA_DIR override when the file exists there."""
    # Plant an override file in DATA_DIR/agents/
    override_dir = council_data_dir / "agents"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_file = override_dir / "phase1_plan.yaml"
    override_file.write_text("# override\n")

    import engine.paths as paths_mod
    importlib.reload(paths_mod)

    resolved = paths_mod.resolve("agents", "phase1_plan.yaml")
    assert resolved == override_file


def test_resolve_falls_back_to_repo_root(council_data_dir):
    """resolve() returns the REPO_ROOT copy when there is no DATA_DIR override."""
    import engine.paths as paths_mod
    importlib.reload(paths_mod)

    # phase1_plan.yaml exists in the repo but NOT in the empty council_data_dir
    resolved = paths_mod.resolve("agents", "phase1_plan.yaml")
    assert resolved == paths_mod.REPO_ROOT / "agents" / "phase1_plan.yaml"
    assert resolved.exists()


def test_init_data_dirs_creates_subdirs(council_data_dir):
    """init_data_dirs() creates the expected sub-directories under DATA_DIR."""
    import engine.paths as paths_mod
    importlib.reload(paths_mod)

    paths_mod.init_data_dirs()

    expected = ["logs", "memory_db", "messages", "workspace", "shared_knowledge", "agents", "flows", "config"]
    for name in expected:
        assert (council_data_dir / name).is_dir(), f"Expected {name}/ to be created"
