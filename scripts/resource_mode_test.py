#!/usr/bin/env python3
"""Regression test for SCORE_ONLY -> SCORE_AUDIO capability upgrade.

This test uses repository fixtures only. It never calls a model API and it
cleans every generated song/preparation/export after completion.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "animal_band.py"
WORKSPACE = ROOT / "workspace"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def call(*args: str, expect_ok: bool = True) -> dict:
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"CLI stdout 不是 JSON：{result.stdout!r}; stderr={result.stderr!r}"
        ) from error
    if bool(payload.get("ok")) != expect_ok:
        raise AssertionError(
            f"CLI {args[0]} 结果异常：{payload}; stderr={result.stderr}"
        )
    return payload


def cleanup(song_id: str | None, preparation_id: str | None) -> None:
    if song_id:
        shutil.rmtree(WORKSPACE / "songs" / song_id, ignore_errors=True)
    if preparation_id:
        (WORKSPACE / "preparations" / f"{preparation_id}.json").unlink(missing_ok=True)
        shutil.rmtree(WORKSPACE / "preparations" / preparation_id, ignore_errors=True)
        shutil.rmtree(WORKSPACE / "exports" / preparation_id, ignore_errors=True)
        (WORKSPACE / "exports" / f"animal-band-classroom-{preparation_id}.zip").unlink(missing_ok=True)


def main() -> int:
    song_id = None
    preparation_id = None
    try:
        with tempfile.TemporaryDirectory(prefix="animal-band-resource-mode-") as temp_name:
            temp = Path(temp_name)
            image = temp / "score.png"
            image.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            ))

            recognized = call(
                "recognize-score",
                "--score-image", str(image),
                "--title", "祖国祖国我们爱你 Score Only",
                "--inference-input", str(ROOT / "demo" / "golden-path" / "recognition-raw.fixture.json"),
            )
            data = recognized["data"]
            song_id = data["song"]["songId"]
            check("SCORE_ONLY recognized", data["resourceMode"] == "SCORE_ONLY")
            check("audio optional", data["hasOriginalAudio"] is False)
            check(
                "score-only activities",
                data["availableActivities"] == ["rhythm_learning", "singing", "sticker_arrangement"],
                json.dumps(data["availableActivities"], ensure_ascii=False),
            )
            check(
                "audio activities locked",
                set(data["lockedActivities"]) == {"listen", "melody_trace", "ensemble"},
            )
            check("AI result stays draft", data["draftScore"]["verificationStatus"] == "draft")

            call(
                "update-score",
                "--song-id", song_id,
                "--score-json", str(ROOT / "demo" / "golden-path" / "zuguo-verified-score.fixture.json"),
            )
            call("verify-score", "--song-id", song_id, "--confirmed", "true", "--reviewer", "resource-mode-test")

            status = call("score-status", "--song-id", song_id)["data"]
            check("score-only does not require alignment", status["measureAlignmentRequired"] is False)
            check("score-only alignment gate satisfied", status["measureAlignmentReady"] is True)

            call("analyze-song", "--song-id", song_id)

            locked = call(
                "generate-recipe",
                "--song-id", song_id,
                "--activities", "listen",
                expect_ok=False,
            )
            check("locked activity rejected", locked["error"]["code"] == "ACTIVITY_REQUIRES_AUDIO")

            recipe = call(
                "generate-recipe",
                "--song-id", song_id,
                "--activities", "rhythm_learning,singing,sticker_arrangement",
            )
            preparation_id = recipe["data"]["preparation"]["preparationId"]
            check("recipe remains human-reviewed", recipe["data"]["lessonRecipe"]["reviewStatus"] == "NOT_REVIEWED")
            call(
                "confirm-recipe",
                "--preparation-id", preparation_id,
                "--confirmed", "true",
                "--reviewer", "resource-mode-test",
            )

            verified_score = json.loads(
                (WORKSPACE / "songs" / song_id / "verified-score.json").read_text(encoding="utf-8")
            )
            measure_numbers = [int(item["number"]) for item in verified_score["measures"]]
            arrangement_input = {
                "harmony": [
                    {"measure": number, "degree": 1, "quality": "major"}
                    for number in measure_numbers
                ],
                "measurePlans": [
                    {"measure": number, "drums": "light", "keys": "hold", "bass": "root", "sax": "melody"}
                    for number in measure_numbers
                ],
                "notes": ["resource mode fixture"],
            }
            arrangement_path = temp / "arrangement.json"
            arrangement_path.write_text(json.dumps(arrangement_input, ensure_ascii=False), encoding="utf-8")
            call("import-arrangement-plan", "--song-id", song_id, "--plan-json", str(arrangement_path))

            prepared = call("prepare-classroom", "--preparation-id", preparation_id)["data"]
            check("prepare without alignment", prepared["resourceMode"] == "SCORE_ONLY")
            check("no listening plan in score-only recipe", prepared["listeningBodyPlan"] is None)
            check("no melody trace plan in score-only recipe", prepared["melodyTracePlan"] is None)
            check("sticker event pack generated", len(prepared["arrangementEventPack"]["tracks"]) == 4)

            readiness = call("check-readiness", "--preparation-id", preparation_id)["data"]["readiness"]
            check("score-only readiness", readiness["ready"] is True, json.dumps(readiness.get("blockers", []), ensure_ascii=False))
            check(
                "readiness has no global audio blocker",
                all(item.get("id") != "ORIGINAL_AUDIO_READY" for item in readiness.get("checks", [])),
            )
            check(
                "readiness has no global alignment blocker",
                all(item.get("id") != "MEASURE_ALIGNMENT_READY" for item in readiness.get("checks", [])),
            )

            exported = call("export-classroom", "--preparation-id", preparation_id)["data"]
            session = json.loads((Path(exported["directory"]) / "offline" / "session.json").read_text(encoding="utf-8"))
            exported_song = session["songs"][0]
            check("static export has no original audio", not exported_song.get("assets", {}).get("originalAudio"))
            check(
                "static export preserves score-only activities",
                session["preparations"][0]["selectedActivities"] == ["rhythm_learning", "singing", "sticker_arrangement"],
            )

            audio = temp / "audio.mp3"
            audio.write_bytes(b"ID3")
            upgraded = call("add-audio", "--song-id", song_id, "--audio", str(audio))["data"]
            check("upgrade to SCORE_AUDIO", upgraded["resourceMode"] == "SCORE_AUDIO")
            check("all six activities unlocked", len(upgraded["availableActivities"]) == 6)
            check("alignment required after upgrade", upgraded["measureAlignmentRequired"] is True)

            upgraded_status = call("score-status", "--song-id", song_id)["data"]
            check("verified score preserved on upgrade", upgraded_status["verificationStatus"] == "verified")
            check("new audio needs fresh alignment", upgraded_status["measureAlignmentReady"] is False)

        print(json.dumps({
            "status": "PASS",
            "checks": len(RESULTS),
            "results": [{"name": n, "ok": ok, "detail": detail} for n, ok, detail in RESULTS],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({
            "status": "FAIL",
            "error": str(error),
            "checks": len(RESULTS),
            "results": [{"name": n, "ok": ok, "detail": detail} for n, ok, detail in RESULTS],
        }, ensure_ascii=False, indent=2))
        return 1
    finally:
        cleanup(song_id, preparation_id)


if __name__ == "__main__":
    raise SystemExit(main())
