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

from score_recognition.inference_assembler import InferenceAssemblyError, assemble_inference  # noqa: E402
from score_recognition.recognition_plan import pillow_available, prepare_recognition_plan  # noqa: E402


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    if not pillow_available():
        print(json.dumps({"status": "SKIP", "reason": "Pillow unavailable"}, ensure_ascii=False))
        return 0
    from PIL import Image, ImageDraw

    with tempfile.TemporaryDirectory(prefix="animal-band-rec-v3-") as temp_name:
        temp = Path(temp_name)
        image_path = temp / "score.png"
        image = Image.new("RGB", (760, 820), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((240, 20, 520, 55), fill="black")
        for top in (155, 275, 395, 515, 635):
            draw.rectangle((45, top, 715, top + 18), fill="black")
            draw.rectangle((60, top + 36, 700, top + 53), fill="black")
            for x in (190, 350, 525, 700):
                draw.rectangle((x, top - 5, x + 2, top + 58), fill="black")
        image.save(image_path)

        plan = prepare_recognition_plan(image_path, temp / "plan")
        assert plan["strategy"] == "music_systems", plan
        expected = plan["coverage"]["expectedSystems"]
        assert expected == 5, plan
        import hashlib
        assert plan["sourceSha256"] == hashlib.sha256(image_path.read_bytes()).hexdigest(), plan

        results = temp / "results"
        results.mkdir()
        write(results / "header.json", {"schema":"animal-band-score-header-v3","regionId":"header","title":"测试歌","tonic":"C","mode":"major","meter":"2/4","bpm":None})
        for index in range(1, expected):
            write(results / f"system-{index:02d}.json", {"schema":"animal-band-score-region-v3","regionId":f"system-{index:02d}","systemIndex":index,"measures":[{"x":[[1,0,1],[2,0,1]],"l":[],"u":[],"w":[]}]})

        try:
            assemble_inference(plan, inference_dir=results)
            raise AssertionError("missing system should fail")
        except InferenceAssemblyError as error:
            assert error.code == "SCORE_SOURCE_COVERAGE_INCOMPLETE", error.code
            assert error.report["repairRegionIds"] == ["system-05"], error.report

        write(results / "system-05.json", {"schema":"animal-band-score-region-v3","regionId":"system-05","systemIndex":5,"measures":[{"x":[[1,0,1],[2,0,1]],"l":[],"u":[],"w":[]}]})
        raw, report = assemble_inference(plan, inference_dir=results)
        assert report["ok"] is True, report
        assert report["systemCount"] == 5, report
        assert raw["schema"] == "animal-band-score-systems-v1", raw
        assert len(raw["systems"]) == 5, raw
        assert raw.get("meter") == "2/4", raw

    print(json.dumps({"status":"PASS","perRegionAssembly":True,"targetedRepair":True,"sourceCoverage":True,"modelMergeRequired":False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
