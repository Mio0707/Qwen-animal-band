#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from node_runtime import resolve_node  # noqa: E402

CLI = ROOT / "scripts" / "animal_band.py"
CANONICAL_CLI = RUNTIME / "animal_band_cli.py"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def call(*args: str, expect_ok: bool = True) -> dict:
    result = subprocess.run([sys.executable, str(CLI), *args], cwd=ROOT, text=True, capture_output=True, env=os.environ.copy())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"CLI stdout 不是 JSON：{result.stdout!r}; stderr={result.stderr!r}") from error
    if bool(payload.get("ok")) != expect_ok:
        raise AssertionError(f"CLI {args[0]} 结果异常：{payload}; stderr={result.stderr}")
    return payload


def import_graph_ready() -> bool:
    root = ROOT / "classroom" / "app"
    pattern = re.compile(r"(?:from\s+|import\s*)[\"']([^\"']+)[\"']")
    for source in root.rglob("*.js"):
        for target in pattern.findall(source.read_text(encoding="utf-8")):
            if not target.startswith("."):
                continue
            path = (source.parent / target.split("?", 1)[0]).resolve()
            if not path.is_file():
                return False
    return True


def bridge_json(url: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> int:
    generated_song = None
    generated_preparation = None
    try:
        layout = [
            ROOT / "SKILL.md", ROOT / "README.md", CLI, CANONICAL_CLI, ROOT / "runtime" / "engine",
            ROOT / "classroom" / "app", ROOT / "classroom" / "web_audio",
            ROOT / "assets" / "web-sampler-v1" / "sample-library.json", ROOT / "review" / "score" / "index.html",
            ROOT / "runtime" / "review_bridge.py", ROOT / "runtime" / "node_runtime.py",
        ]
        check("repo layout", all(path.exists() for path in layout), "发行文件缺失")
        check("Python imports", CLI.is_file() and CANONICAL_CLI.is_file() and (ROOT / "runtime" / "repositories" / "song_repository.py").is_file())
        node = resolve_node()
        check("Node available", bool(node), "请安装 Node.js；桌面宿主会自动搜索常见安装位置")
        check("QwenWork inference importer", (ROOT / "runtime" / "score_recognition" / "skill_score_importer.py").is_file())
        runtime_sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "runtime").rglob("*.py"))
        forbidden_credentials = ("DASH" + "SCOPE_API_KEY", "Author" + "ization\": f\"Bearer")
        check("Runtime has no model API key dependency", all(value not in runtime_sources for value in forbidden_credentials))
        curriculum = json.loads((ROOT / "runtime" / "curriculum" / "stage1.json").read_text(encoding="utf-8"))
        check("Curriculum load", curriculum.get("stage_id") == "stage_1")
        library = json.loads((ROOT / "assets" / "web-sampler-v1" / "sample-library.json").read_text(encoding="utf-8"))
        samples = [sample for instrument in library.get("instruments", {}).values() for sample in instrument.get("samples", [])]
        check("Web Sampler library parse", set(library.get("instruments", {})) == {"dog", "bear", "cat", "lion"})
        check("31 MP3 samples exist", len(samples) == 31 and all((ROOT / "assets" / "web-sampler-v1" / sample["path"]).is_file() for sample in samples))
        check("Sample ranges valid", all(0 <= int(sample["midi"]) <= 127 for sample in samples))
        check("Classroom import graph", import_graph_ready())
        for source in [*list((ROOT / "classroom" / "web_audio").glob("*.js")), ROOT / "classroom" / "app" / "teacher" / "sticker-arrangement-controller.js"]:
            syntax = subprocess.run([node, "--check", str(source)], text=True, capture_output=True)
            check(f"Web Audio syntax {source.name}", syntax.returncode == 0, syntax.stderr.strip())
        scheduler = (ROOT / "classroom" / "web_audio" / "event_scheduler.js").read_text(encoding="utf-8")
        check("AudioContext clock", "currentTime" in scheduler and "setTimeout" not in scheduler)
        offline_function = (ROOT / "classroom" / "app" / "classroom" / "api.js").read_text(encoding="utf-8").split("export async function", 1)[0]
        check("Offline route has no classroom API dependency", "/api/classroom/sessions" not in offline_function)
        review_sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "review" / "score").rglob("*.js"))
        check("Review UI has no legacy API dependency", "/api/songs" not in review_sources and "/api/qwen" not in review_sources)

        with tempfile.TemporaryDirectory(prefix="animal-band-smoke-") as temp_name:
            temp = Path(temp_name)
            image = temp / "score.png"
            image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
            audio = temp / "audio.mp3"; audio.write_bytes(b"ID3")
            recognized = call("recognize-score", "--score-image", str(image), "--audio", str(audio), "--title", "祖国祖国我们爱你 Smoke", "--inference-input", str(ROOT / "demo" / "golden-path" / "recognition-raw.fixture.json"))
            check("QwenWork score inference stays draft", recognized["data"]["draftScore"]["verificationStatus"] == "draft")
            generated_song = recognized["data"]["song"]["songId"]
            call("update-score", "--song-id", generated_song, "--score-json", str(ROOT / "demo" / "golden-path" / "zuguo-verified-score.fixture.json"))
            gate = call("verify-score", "--song-id", generated_song, "--confirmed", "false", expect_ok=False)
            check("Score human gate", gate["error"]["code"] == "HUMAN_CONFIRMATION_REQUIRED")
            call("verify-score", "--song-id", generated_song, "--confirmed", "true", "--reviewer", "smoke-test")
            analyzed = call("analyze-song", "--song-id", generated_song)
            check("Material Matcher", bool(analyzed["data"]["materialMatch"]))
            check("Learning Profile", analyzed["data"]["learningProfile"].get("generationStatus") == "READY")

            token = "smoke-token-1234567890-1234567890"
            port_file = temp / "bridge.json"
            bridge = subprocess.Popen([sys.executable, str(ROOT / "runtime" / "review_bridge.py"), "--song-id", generated_song, "--token", token, "--port-file", str(port_file), "--idle-timeout", "120"], cwd=ROOT)
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not port_file.is_file() and bridge.poll() is None: time.sleep(0.05)
                check("Review Bridge starts", port_file.is_file(), "loopback socket unavailable")
                port = json.loads(port_file.read_text(encoding="utf-8"))["port"]
                base = f"http://127.0.0.1:{port}"
                status, _ = bridge_json(f"{base}/bridge/status")
                check("Review Bridge token required", status == 403)
                status, bridge_status = bridge_json(f"{base}/bridge/status?token={token}")
                check("Review Bridge loopback only", status == 200 and bridge_status["data"]["loopbackOnly"] is True)
                with urlopen(f"{base}/review/score/?songId={generated_song}&token={token}", timeout=5) as response:
                    page = response.read().decode("utf-8")
                check("review/score page resources complete", "score_review.js" in page and "score_review.css" in page)
                _, loaded = bridge_json(f"{base}/bridge/score?songId={generated_song}&token={token}")
                bridge_score = loaded["data"]["score"]
                bridge_score["title"] += " Bridge Edit"
                _, saved = bridge_json(f"{base}/bridge/score/draft?songId={generated_song}&token={token}", method="PUT", body=bridge_score)
                check("Draft saves through shared workspace", saved["data"]["score"]["verificationStatus"] == "draft")
                song_state = json.loads((ROOT / "workspace" / "songs" / generated_song / "song.json").read_text(encoding="utf-8"))
                check("Page edit makes downstream stale", song_state.get("materialMatchStatus") == "STALE" and song_state.get("learningProfileStatus") == "STALE")
                draft = saved["data"]["score"]
                _, reviewed = bridge_json(f"{base}/bridge/score/reviewed?songId={generated_song}&token={token}", method="PUT", body=draft)
                check("Reviewed saves", reviewed["data"]["score"]["verificationStatus"] == "reviewed")
                reviewed_score = reviewed["data"]["score"]; reviewed_score.update({"verificationStatus": "verified", "verifiedBy": "smoke-review"})
                _, verified = bridge_json(f"{base}/bridge/score/verified?songId={generated_song}&token={token}", method="PUT", body=reviewed_score)
                check("Verified saves", verified["data"]["score"]["verificationStatus"] == "verified")
                alignment = {"schemaVersion": "2.0.0", "songId": generated_song, "calibration": {"startMeasure": 1, "endMeasure": 4, "startSec": 7.901, "endSec": 11.851}, "anchors": [], "segments": []}
                _, aligned = bridge_json(f"{base}/bridge/measure-alignment?songId={generated_song}&token={token}", method="PUT", body=alignment)
                check("Measure Alignment saves", aligned["data"]["alignment"]["calibrationStatus"] == "teacher_verified")
                cli_status = call("score-status", "--song-id", generated_song)
                check("Review and CLI share workspace", cli_status["data"]["verificationStatus"] == "verified" and cli_status["data"]["measureAlignmentReady"] is True)
                close_status, _ = bridge_json(f"{base}/bridge/close?token={token}", method="POST", body={})
                check("Review Bridge closes", close_status == 200)
                bridge.wait(timeout=5)
            finally:
                if bridge.poll() is None: bridge.terminate(); bridge.wait(timeout=5)

            analyzed = call("analyze-song", "--song-id", generated_song)
            recipe = call("generate-recipe", "--song-id", generated_song, "--activities", ",".join(("listen", "melody_trace", "rhythm_learning", "singing", "ensemble", "sticker_arrangement")))
            generated_preparation = recipe["data"]["preparation"]["preparationId"]
            check("Lesson Recipe", recipe["data"]["lessonRecipe"].get("reviewStatus") == "NOT_REVIEWED")
            gate = call("confirm-recipe", "--preparation-id", generated_preparation, "--confirmed", "false", expect_ok=False)
            check("Recipe human gate", gate["error"]["code"] == "HUMAN_CONFIRMATION_REQUIRED")
            call("confirm-recipe", "--preparation-id", generated_preparation, "--confirmed", "true", "--reviewer", "smoke-test")
            arrangement_gate = call("prepare-classroom", "--preparation-id", generated_preparation, expect_ok=False)
            check("Arrangement inference gate", arrangement_gate["error"]["code"] == "ARRANGEMENT_INFERENCE_REQUIRED")
            context = call("arrangement-context", "--song-id", generated_song)
            check("Arrangement inference runs in Skill layer", context["data"]["inferenceLayer"] == "qwenwork_skill")
            verified_score = json.loads((ROOT / "workspace" / "songs" / generated_song / "verified-score.json").read_text(encoding="utf-8"))
            measure_numbers = [int(item["number"]) for item in verified_score["measures"]]
            arrangement_input = {
                "harmony": [{"measure": number, "degree": 1, "quality": "major"} for number in measure_numbers],
                "measurePlans": [{"measure": number, "drums": "light", "keys": "hold", "bass": "root", "sax": "melody"} for number in measure_numbers],
                "notes": ["offline contract fixture"],
            }
            arrangement_path = temp / "arrangement-inference.json"
            arrangement_path.write_text(json.dumps(arrangement_input, ensure_ascii=False), encoding="utf-8")
            imported_arrangement = call("import-arrangement-plan", "--song-id", generated_song, "--plan-json", str(arrangement_path))
            check("Arrangement inference import", imported_arrangement["data"]["inferenceLayer"] == "qwenwork_skill")
            status_after_review = call("score-status", "--song-id", generated_song)
            check("Golden score review status", status_after_review["data"]["measureAlignmentReady"] is True)
            prepared = call("prepare-classroom", "--preparation-id", generated_preparation)
            tracks = prepared["data"]["arrangementEventPack"]["tracks"]
            check("Arrangement compiler uses imported plan", prepared["data"]["arrangementEventPack"]["generator"]["type"] == "qwenwork_skill_arrangement")
            check("Sticker Event JSON has four tracks", [track["trackId"] for track in tracks] == ["dog", "bear", "cat", "lion"] and all(isinstance(track.get("events"), list) for track in tracks))
            readiness = call("check-readiness", "--preparation-id", generated_preparation)
            check("WEB_SAMPLER_READY", any(item["id"] == "WEB_SAMPLER_READY" and item["ok"] for item in readiness["data"]["readiness"]["checks"]))
            check("Golden fixture readiness", readiness["data"]["readiness"]["ready"], json.dumps(readiness["data"]["readiness"].get("blockers", []), ensure_ascii=False))
            exported = call("export-classroom", "--preparation-id", generated_preparation)
            export_dir = Path(exported["data"]["directory"])
            check("Static export basic fixture", (export_dir / "index.html").is_file() and (export_dir / "offline" / "session.json").is_file())
            check("Static classroom visual assets", (export_dir / "app" / "content-factory" / "assets" / "avatar-dog.png").is_file())
            check("Static classroom serverless", "/api/classroom/sessions" not in (export_dir / "offline" / "session.json").read_text(encoding="utf-8"))

        print("Animal Band release smoke test")
        for name, ok, detail in RESULTS:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}{f': {detail}' if detail else ''}")
        print("INFERENCE_LAYER = QWENWORK_SKILL")
        print(f"PASS ({len(RESULTS)} checks)")
        return 0
    except Exception as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        for name, ok, detail in RESULTS:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}{f': {detail}' if detail else ''}")
        return 1


if __name__ == "__main__": raise SystemExit(main())
