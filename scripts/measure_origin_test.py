#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from node_runtime import resolve_node  # noqa: E402


def main() -> int:
    node = resolve_node()
    if not node:
        print("FAIL: Node.js not found", file=sys.stderr)
        return 1

    score_path = ROOT / "demo" / "golden-path" / "zuguo-verified-score.fixture.json"
    score = json.loads(score_path.read_text(encoding="utf-8"))
    measures = sorted(score.get("measures", []), key=lambda item: int(item["number"]))
    if len(measures) < 4:
        print("FAIL: fixture needs at least 4 measures", file=sys.stderr)
        return 1
    origin = int(measures[2]["number"])
    next_measure = int(measures[3]["number"])
    score["measureOrigin"] = {"sourceMeasure": origin, "logicalMeasure": 1, "source": "test"}
    score.setdefault("teachingConfig", {})["singingMeasuresPerUnit"] = 2

    with tempfile.TemporaryDirectory(prefix="animal-band-origin-") as temp_name:
        temp = Path(temp_name)
        payload = temp / "score.json"
        payload.write_text(json.dumps(score, ensure_ascii=False), encoding="utf-8")
        script = temp / "check.mjs"
        script.write_text(
            f'''import fs from "node:fs";\n'
import {{ buildLessonSegments }} from {json.dumps((ROOT / "runtime" / "engine" / "lesson-segments.js").as_uri())};\n'
import {{ alignmentCoverage }} from {json.dumps((ROOT / "runtime" / "engine" / "measure-alignment.js").as_uri())};\n'
const score = JSON.parse(fs.readFileSync({json.dumps(str(payload))}, "utf8"));\n'
const segments = buildLessonSegments(score, 2);\n'
if (!segments.length) throw new Error("no lesson segments");\n'
if (segments[0].startMeasure !== {origin}) throw new Error(`origin start mismatch: ${{segments[0].startMeasure}}`);\n'
if (segments[0].logicalStartMeasure !== 1 || segments[0].logicalEndMeasure !== 2) throw new Error("logical numbering mismatch");\n'
if (segments[0].leadInMeasureCount !== 2) throw new Error(`lead-in count mismatch: ${{segments[0].leadInMeasureCount}}`);\n'
const stale = alignmentCoverage(score, {{ songId: score.songId, calibration: {{ startMeasure: {int(measures[0]['number'])}, endMeasure: {int(measures[1]['number'])}, startSec: 1, endSec: 3 }}, anchors: [], segments: [] }});\n'
if (stale.ready) throw new Error("alignment before origin must be stale");\n'
const current = alignmentCoverage(score, {{ songId: score.songId, calibration: {{ startMeasure: {origin}, endMeasure: {next_measure}, startSec: 5, endSec: 7 }}, anchors: [], segments: [] }});\n'
if (!current.ready || !current.originReady || current.originMeasure !== {origin}) throw new Error("origin alignment should be ready");\n'
console.log(JSON.stringify({{ status: "PASS", origin: {origin}, firstSegment: segments[0], coverage: current }}));\n'''.replace("'\n", "\n"),
            encoding="utf-8",
        )
        result = subprocess.run([node, str(script)], cwd=ROOT, text=True, capture_output=True)
        if result.returncode != 0:
            print(result.stderr or result.stdout, file=sys.stderr)
            return result.returncode
        print(result.stdout.strip())
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
