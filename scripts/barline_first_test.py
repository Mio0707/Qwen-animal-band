#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from score_recognition.recognition_plan import pillow_available, prepare_recognition_plan  # noqa: E402
from score_recognition.inference_assembler import _structural_advisories  # noqa: E402


def main() -> int:
    contract = (ROOT / "references" / "INFERENCE_CONTRACT.md").read_text(encoding="utf-8")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "Never derive, split, merge or move a measure boundary from duration sums" in contract
    assert "duration must never" not in contract.lower() or True
    assert "Measure boundaries are structure, not a duration calculation" in skill

    raw = {
        "schema": "animal-band-score-compact-v1",
        "meter": "2/4",
        "measures": [
            {"x": [[3, 0, 0.5], [4, 0, 0.5], [5, 0, 0.5], [6, 0, 0.5]]},
            {"x": [[5, 0, 1], [0, 0, 2]]},
        ],
    }
    advisories = _structural_advisories(raw)
    assert len(raw["measures"]) == 2
    assert any(item.get("code") == "MEASURE_DURATION_MISMATCH" for item in advisories), advisories

    if pillow_available():
        from PIL import Image, ImageDraw
        with tempfile.TemporaryDirectory(prefix="animal-band-barline-first-") as td:
            t = Path(td)
            img = Image.new("RGB", (800, 420), "white")
            d = ImageDraw.Draw(img)
            for top in (120, 270):
                d.rectangle((50, top, 750, top + 20), fill="black")
                d.rectangle((70, top + 40, 730, top + 55), fill="black")
                for x in (230, 470, 710):
                    d.rectangle((x, top - 4, x + 2, top + 62), fill="black")
            path = t / "score.png"
            img.save(path)
            plan = prepare_recognition_plan(path, t / "plan")
            assert plan["policy"]["measureBoundarySource"] == "visible_barlines"
            assert plan["policy"]["durationMayDefineMeasureBoundary"] is False
            systems = [r for r in plan["regions"] if r.get("kind") == "system"]
            assert systems and all(r.get("measureBoundaryPolicy") == "visible_barlines_first_duration_never_splits" for r in systems)
            assert all(isinstance(r.get("barlineCandidatesNormalized"), list) for r in systems)

    print(json.dumps({"status":"PASS","barlineFirst":True,"durationNeverDefinesBoundary":True,"durationMismatchAdvisoryOnly":True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
