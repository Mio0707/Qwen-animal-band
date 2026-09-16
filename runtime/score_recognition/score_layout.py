"""Backward-compatible wrapper around Recognition Pipeline v3 planning."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .recognition_plan import (
        PLAN_SCHEMA,
        compatibility_layout_manifest,
        pillow_available,
        prepare_recognition_plan,
    )
except ImportError:  # direct-script compatibility
    from recognition_plan import (
        PLAN_SCHEMA, compatibility_layout_manifest, pillow_available, prepare_recognition_plan,
    )


def prepare_score_image(image_path: Path, output_dir: Path) -> dict[str, Any]:
    """Legacy name retained for callers; returns the v3 recognition plan."""
    return prepare_recognition_plan(image_path, output_dir)


def validate_source_coverage(raw: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate aggregate raw inference against either v3 plan or v2 manifest."""
    strategy = manifest.get("strategy")
    if strategy != "music_systems":
        return {
            "ok": True,
            "strategy": strategy,
            "expectedSystems": None,
            "receivedSystems": None,
            "missingSystems": [],
        }

    if manifest.get("schema") == PLAN_SCHEMA:
        expected = int((manifest.get("coverage") or {}).get("expectedSystems") or 0)
    else:
        expected = int((manifest.get("sourceCoverage") or {}).get("expectedSystems") or 0)
    systems = raw.get("systems") if isinstance(raw, dict) else None
    if raw.get("schema") != "animal-band-score-systems-v1" or not isinstance(systems, list):
        return {
            "ok": False,
            "strategy": strategy,
            "expectedSystems": expected,
            "receivedSystems": 0,
            "missingSystems": list(range(1, expected + 1)),
            "reason": "system-mode plan requires animal-band-score-systems-v1 aggregate inference",
        }
    received = set()
    for item in systems:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("systemIndex"))
        except (TypeError, ValueError):
            continue
        if 1 <= index <= expected and isinstance(item.get("measures"), list) and item.get("measures"):
            received.add(index)
    missing = [index for index in range(1, expected + 1) if index not in received]
    return {
        "ok": not missing,
        "strategy": strategy,
        "expectedSystems": expected,
        "receivedSystems": len(received),
        "missingSystems": missing,
    }


__all__ = [
    "pillow_available",
    "prepare_score_image",
    "prepare_recognition_plan",
    "validate_source_coverage",
    "compatibility_layout_manifest",
]
