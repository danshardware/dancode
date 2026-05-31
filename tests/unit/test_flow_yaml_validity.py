"""Smoke tests: flow YAMLs for phase 2 and phase 3 parse cleanly and contain expected refs."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_phase2_jank_yaml_valid() -> None:
    """flows/phase2_jank.yaml parses as valid YAML and contains coding_standards ref."""
    text = (Path(__file__).parent.parent.parent / "flows" / "phase2_jank.yaml").read_text()
    data = yaml.safe_load(text)
    assert data["id"] == "phase2_jank"
    assert "coding_standards" in text


def test_phase3_refine_yaml_valid() -> None:
    """flows/phase3_refine.yaml parses as valid YAML and contains coding_standards ref."""
    text = (Path(__file__).parent.parent.parent / "flows" / "phase3_refine.yaml").read_text()
    data = yaml.safe_load(text)
    assert data["id"] == "phase3_refine"
    assert "coding_standards" in text
