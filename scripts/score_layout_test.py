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
from score_recognition.score_layout import validate_source_coverage  # noqa: E402


def main() -> int:
    if not pillow_available():
        print(json.dumps({"status": "SKIP", "reason": "Pillow unavailable; runtime falls back to whole_page"}, ensure_ascii=False))
        return 0
    from PIL import Image, ImageDraw

    with tempfile.TemporaryDirectory(prefix="animal-band-layout-test-") as temp_name:
        temp = Path(temp_name)
        image_path = temp / "score.png"
        image = Image.new("RGB", (720, 760), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((260, 25, 460, 55), fill="black")
        for top in (150, 265, 380, 495, 610):
            draw.rectangle((45, top, 675, top + 18), fill="black")
            draw.rectangle((70, top + 34, 650, top + 50), fill="black")
            for x in (180, 330, 500, 650):
                draw.rectangle((x, top - 4, x + 2, top + 54), fill="black")
        image.save(image_path)

        plan = prepare_recognition_plan(image_path, temp / "layout")
        assert plan["schema"] == "animal-band-recognition-plan-v3", plan
        assert plan["strategy"] == "music_systems", plan
        assert plan["coverage"]["expectedSystems"] == 5, plan

        complete = {"schema":"animal-band-score-systems-v1","systems":[{"systemIndex":index,"measures":[{"x":[[1,0,1]]}]} for index in range(1,6)]}
        incomplete = dict(complete)
        incomplete["systems"] = complete["systems"][:-1]
        assert validate_source_coverage(complete, plan)["ok"] is True
        missing = validate_source_coverage(incomplete, plan)
        assert missing["ok"] is False and missing["missingSystems"] == [5], missing

    print(json.dumps({"status":"PASS","systems":5,"coverageGate":True,"planSchema":"v3"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
