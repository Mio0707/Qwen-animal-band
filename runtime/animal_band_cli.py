#!/usr/bin/env python3
"""Single JSON CLI for the Animal Band QwenWork release runtime."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
WORKSPACE = ROOT / "workspace"
for candidate in (ROOT, RUNTIME, RUNTIME / "score_recognition"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from listening_warmup_generator import generate_listening_body_plan  # noqa: E402
from repositories.persistence_utils import atomic_write_json, read_json, utc_now  # noqa: E402
from repositories.preparation_repository import PreparationRepository  # noqa: E402
from repositories.song_repository import SongRepository  # noqa: E402
from score_recognition.skill_score_importer import run_recognition  # noqa: E402
from sticker_arrangement_generator import arrangement_prompt, generate_sticker_stem_plan, normalize_arrangement_plan, validate_arrangement_plan  # noqa: E402

ACTIVITIES = ("listen", "melody_trace", "rhythm_learning", "singing", "ensemble", "sticker_arrangement")


class CliError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliError("INVALID_ARGUMENT", message)


def repositories() -> tuple[SongRepository, PreparationRepository]:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    return SongRepository(WORKSPACE), PreparationRepository(WORKSPACE)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, value)


def node_pipeline(operation: str, payload: dict) -> dict:
    node = os.environ.get("ANIMAL_BAND_NODE") or shutil.which("node")
    if not node:
        raise CliError("NODE_NOT_FOUND", "未找到 Node.js；请安装 Node.js 或设置 ANIMAL_BAND_NODE。")
    command = [node, str(RUNTIME / "engine" / "pipeline-cli.js"), operation]
    result = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True, cwd=ROOT)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Engine 执行失败").strip().splitlines()[-1]
        raise CliError("ENGINE_ERROR", message)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CliError("ENGINE_PROTOCOL_ERROR", "Engine 没有返回有效 JSON。") from error
    if not isinstance(value, dict):
        raise CliError("ENGINE_PROTOCOL_ERROR", "Engine 返回值必须是 JSON 对象。")
    return value


def require_song(repo: SongRepository, song_id: str) -> dict:
    song = repo.get_song_by_id(song_id)
    if not song:
        raise CliError("SONG_NOT_FOUND", f"歌曲不存在：{song_id}")
    return song


def require_preparation(repo: PreparationRepository, preparation_id: str) -> dict:
    preparation = repo.get_preparation_by_id(preparation_id)
    if not preparation:
        raise CliError("PREPARATION_NOT_FOUND", f"备课不存在：{preparation_id}")
    return preparation


def require_verified_score(repo: SongRepository, song_id: str) -> dict:
    score = repo.get_verified_score(song_id)
    if not score or score.get("verificationStatus") != "verified":
        raise CliError("SCORE_NOT_VERIFIED", "请先由教师明确确认简谱。")
    return score


def command_doctor(_: argparse.Namespace) -> dict:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "doctor.py"), "--json"], text=True, capture_output=True, cwd=ROOT)
    if result.returncode not in (0, 1):
        raise CliError("DOCTOR_FAILED", (result.stderr or "doctor 执行失败").strip())
    return json.loads(result.stdout)


def command_recognize(args: argparse.Namespace) -> dict:
    score_image, audio = Path(args.score_image).expanduser().resolve(), Path(args.audio).expanduser().resolve()
    if not score_image.is_file() or not audio.is_file():
        raise CliError("SOURCE_FILE_MISSING", "简谱图片或歌曲音频不存在。")
    songs, _ = repositories()
    song = songs.create_song(args.title, "stage_1", {}, (audio.name, audio.read_bytes()), (score_image.name, score_image.read_bytes()))
    inference_input = Path(args.inference_input).expanduser().resolve()
    try:
        score = run_recognition(score_image, song["songId"], WORKSPACE / "songs", title=args.title, raw_input=inference_input)
        songs.save_score(song["songId"], score)
    except Exception:
        shutil.rmtree(WORKSPACE / "songs" / song["songId"], ignore_errors=True)
        raise
    return {"song": songs.get_song_by_id(song["songId"]), "draftScore": score, "humanReviewRequired": True}


def command_update_score(args: argparse.Namespace) -> dict:
    songs, _ = repositories()
    song = require_song(songs, args.song_id)
    score = read_json(Path(args.score_json).expanduser().resolve())
    score["songId"] = song["songId"]
    score["title"] = song["title"]
    score["verificationStatus"] = "draft"
    score["verifiedBy"] = None
    score["verifiedAt"] = None
    score.setdefault("source", {})["humanReviewed"] = False
    score["source"]["reviewedAt"] = None
    songs.save_score(song["songId"], score)
    return {"songId": song["songId"], "draftScore": score, "humanReviewRequired": True}


def command_verify_score(args: argparse.Namespace) -> dict:
    if not args.confirmed:
        raise CliError("HUMAN_CONFIRMATION_REQUIRED", "verify-score 必须提供 --confirmed true。")
    songs, preparations = repositories()
    score = songs.get_score(args.song_id)
    if not score or score.get("verificationStatus") not in {"draft", "reviewed"}:
        raise CliError("DRAFT_SCORE_REQUIRED", "没有可供教师确认的 Draft Score。")
    blockers = [item for item in score.get("warnings", []) if item.get("severity") == "blocking"]
    if blockers:
        raise CliError("BLOCKING_SCORE_WARNINGS", f"仍有 {len(blockers)} 个阻断项，请先 update-score 修正。")
    verified = deepcopy(score)
    verified_at = utc_now()
    verified.update({"verificationStatus": "verified", "verifiedBy": args.reviewer, "verifiedAt": verified_at})
    verified.setdefault("source", {}).update({"humanReviewed": True, "reviewedAt": verified_at})
    songs.save_score(args.song_id, verified)
    preparations.invalidate_for_song(args.song_id)
    return {"songId": args.song_id, "verifiedScore": verified, "gate": "HUMAN_REVIEW_CONFIRMED"}


def command_score_status(args: argparse.Namespace) -> dict:
    songs, _ = repositories()
    require_song(songs, args.song_id)
    score = songs.get_score(args.song_id)
    if not score:
        raise CliError("SCORE_NOT_FOUND", "歌曲尚无可用简谱。")
    alignment = songs.get_artifact(args.song_id, "measure-alignment.json")
    calibration = (alignment or {}).get("calibration") or {}
    alignment_ready = bool(
        alignment
        and alignment.get("sourceScoreVerifiedAt") == score.get("verifiedAt")
        and float(calibration.get("startSec", -1)) >= 0
        and float(calibration.get("endSec", 0)) > float(calibration.get("startSec", 0))
    )
    return {
        "songId": args.song_id,
        "verificationStatus": score.get("verificationStatus"),
        "measureAlignmentReady": alignment_ready,
        "warnings": score.get("warnings", []),
    }


def command_open_score_review(args: argparse.Namespace) -> dict:
    songs, _ = repositories()
    require_song(songs, args.song_id)
    session_id = uuid4().hex
    token = secrets.token_urlsafe(32)
    port_file = Path(tempfile.gettempdir()) / f"animal-band-review-{session_id}.json"
    idle_timeout = max(30, min(3600, args.idle_timeout))
    process = subprocess.Popen(
        [sys.executable, str(RUNTIME / "review_bridge.py"), "--song-id", args.song_id, "--token", token, "--port-file", str(port_file), "--idle-timeout", str(idle_timeout)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    deadline = time.monotonic() + 5
    port = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        if port_file.is_file():
            try: port = int(json.loads(port_file.read_text(encoding="utf-8"))["port"]); break
            except Exception: pass
        time.sleep(0.05)
    if not port:
        if process.poll() is None: process.terminate()
        raise CliError("REVIEW_BRIDGE_START_FAILED", "专业简谱校对面板启动失败。")
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=idle_timeout)).isoformat().replace("+00:00", "Z")
    review_url = f"http://127.0.0.1:{port}/review/score/?songId={quote(args.song_id)}&token={quote(token)}&mode=teacher"
    return {"reviewUrl": review_url, "sessionId": session_id, "expiresAt": expires_at, "loopbackOnly": True}


def command_analyze(args: argparse.Namespace) -> dict:
    songs, preparations = repositories()
    require_song(songs, args.song_id)
    score = require_verified_score(songs, args.song_id)
    curriculum = read_json(RUNTIME / "curriculum" / "stage1.json")
    match = node_pipeline("match", {"score": score, "curriculum": curriculum})
    profile = node_pipeline("profile", {"match": match, "score": score, "curriculum": curriculum})
    songs.save_artifact(args.song_id, "material-match.json", match)
    songs.save_artifact(args.song_id, "learning-profile.json", profile)
    songs.update_song(args.song_id, {"materialMatchStatus": "READY", "learningProfileStatus": "READY", "processingStatus": "PROFILE_READY"}, internal=True)
    preparations.invalidate_for_song(args.song_id)
    return {"songId": args.song_id, "materialMatch": match, "learningProfile": profile}


def parse_activities(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    invalid = [item for item in values if item not in ACTIVITIES]
    if invalid or not values:
        raise CliError("INVALID_ACTIVITIES", f"课堂活动无效：{', '.join(invalid) if invalid else '至少选择一项'}")
    return list(dict.fromkeys(values))


def command_generate_recipe(args: argparse.Namespace) -> dict:
    songs, preparations = repositories()
    score = require_verified_score(songs, args.song_id)
    profile = songs.get_artifact(args.song_id, "learning-profile.json")
    preparation = preparations.create_preparation(args.song_id, reuse_active=not args.new)
    preparation = preparations.update_preparation(preparation["preparationId"], {"selectedActivities": parse_activities(args.activities)})
    library = read_json(RUNTIME / "teaching_assets" / "stage1-teaching-assets.json")
    recipe = node_pipeline("recipe", {"preparation": preparation, "profile": profile, "score": score, "teachingAssetLibrary": library})
    preparations.save_artifact(preparation["preparationId"], "lesson-recipe.json", recipe)
    preparations.update_preparation(preparation["preparationId"], {
        "lessonRecipeId": recipe["recipeId"],
        "lessonRecipeStatus": "READY" if recipe.get("generationStatus") == "READY_FOR_ASSETS" else "BLOCKED",
        "recipeReviewStatus": "NOT_REVIEWED",
        "readinessStatus": "NOT_EVALUATED",
        "status": "DRAFT",
    }, internal=True)
    return {"preparation": preparations.get_preparation_by_id(preparation["preparationId"]), "lessonRecipe": recipe, "humanReviewRequired": True}


def command_confirm_recipe(args: argparse.Namespace) -> dict:
    if not args.confirmed:
        raise CliError("HUMAN_CONFIRMATION_REQUIRED", "confirm-recipe 必须提供 --confirmed true。")
    _, preparations = repositories()
    preparation = require_preparation(preparations, args.preparation_id)
    recipe = preparations.get_artifact(args.preparation_id, "lesson-recipe.json")
    if not recipe or recipe.get("reviewStatus") != "NOT_REVIEWED":
        raise CliError("RECIPE_NOT_REVIEWABLE", "没有待确认的课堂方案。")
    reviewed_at = utc_now()
    recipe.update({"reviewStatus": "REVIEWED", "reviewedAt": reviewed_at, "reviewedBy": args.reviewer})
    preparations.save_artifact(args.preparation_id, "lesson-recipe.json", recipe)
    adjustments = deepcopy(preparation.get("teacherAdjustments") or {})
    adjustments["recipeReview"] = {"reviewedAt": reviewed_at, "reviewedBy": args.reviewer}
    preparations.update_preparation(args.preparation_id, {"teacherAdjustments": adjustments}, internal=False)
    preparations.update_preparation(args.preparation_id, {"recipeReviewStatus": "REVIEWED", "readinessStatus": "NOT_EVALUATED"}, internal=True)
    return {"preparationId": args.preparation_id, "lessonRecipe": recipe, "gate": "HUMAN_REVIEW_CONFIRMED"}


def command_alignment(args: argparse.Namespace) -> dict:
    songs, preparations = repositories()
    preparation = require_preparation(preparations, args.preparation_id)
    score = require_verified_score(songs, preparation["songId"])
    if args.start_measure > args.end_measure or args.start_sec >= args.end_sec:
        raise CliError("INVALID_ALIGNMENT", "校准范围必须满足 startMeasure <= endMeasure 且 startSec < endSec。")
    numbers = {int(item["number"]) for item in score.get("measures", [])}
    if args.start_measure not in numbers or args.end_measure not in numbers:
        raise CliError("INVALID_ALIGNMENT", "校准小节超出 Verified Score 范围。")
    alignment = {
        "schemaVersion": "2.0.0", "songId": preparation["songId"],
        "sourceScoreVerifiedAt": score["verifiedAt"], "updatedAt": utc_now(),
        "calibration": {"startMeasure": args.start_measure, "endMeasure": args.end_measure, "startSec": args.start_sec, "endSec": args.end_sec},
        "anchors": [], "calibrationStatus": "teacher_verified",
    }
    songs.save_artifact(preparation["songId"], "measure-alignment.json", alignment)
    preparations.invalidate_readiness_for_song(preparation["songId"])
    return {"preparationId": args.preparation_id, "measureAlignment": alignment}


def command_arrangement_context(args: argparse.Namespace) -> dict:
    songs, _ = repositories()
    score = require_verified_score(songs, args.song_id)
    return {
        "songId": args.song_id,
        "sourceScoreVerifiedAt": score.get("verifiedAt"),
        "inferenceLayer": "qwenwork_skill",
        "prompt": arrangement_prompt(score),
    }


def command_import_arrangement(args: argparse.Namespace) -> dict:
    songs, preparations = repositories()
    score = require_verified_score(songs, args.song_id)
    raw = read_json(Path(args.plan_json).expanduser().resolve())
    validate_arrangement_plan(raw, score)
    plan = normalize_arrangement_plan(raw, score)
    artifact = {
        "schemaVersion": "1.0.0",
        "songId": args.song_id,
        "sourceScoreVerifiedAt": score.get("verifiedAt"),
        "inferenceLayer": "qwenwork_skill",
        "plan": plan,
        "importedAt": utc_now(),
    }
    songs.save_artifact(args.song_id, "sticker-arrangement-plan.json", artifact)
    preparations.invalidate_readiness_for_song(args.song_id)
    return artifact


def default_sticker_arrangement(preparation: dict, recipe: dict) -> dict:
    activity = next((item for item in recipe.get("activities", []) if item.get("type") == "sticker_arrangement"), None)
    segments = deepcopy(activity.get("bindings", {}).get("lessonSegments", []) if activity else [])
    track_ids = ["dog", "bear", "cat", "lion"]
    return {
        "schemaVersion": "3.0.0", "runtimeVersion": "3.0.0", "preparationId": preparation["preparationId"],
        "songId": preparation["songId"], "segmentCount": len(segments), "lessonSegments": segments, "trackIds": track_ids,
        "segmentStates": [{"segmentId": segment["segmentId"], "activeTrackIds": track_ids} for segment in segments], "updatedAt": utc_now(),
    }


def command_prepare(args: argparse.Namespace) -> dict:
    songs, preparations = repositories()
    preparation = require_preparation(preparations, args.preparation_id)
    score = require_verified_score(songs, preparation["songId"])
    recipe = preparations.get_artifact(args.preparation_id, "lesson-recipe.json")
    if not recipe or recipe.get("reviewStatus") != "REVIEWED":
        raise CliError("RECIPE_REVIEW_REQUIRED", "请先由教师确认课堂方案。")
    alignment = songs.get_artifact(preparation["songId"], "measure-alignment.json")
    if not alignment:
        raise CliError("MEASURE_ALIGNMENT_REQUIRED", "请先人工校准原曲小节时间。")
    song = require_song(songs, preparation["songId"])
    listening = generate_listening_body_plan(song, score)
    gestures = read_json(RUNTIME / "gestures" / "gesture-library.json")
    trace = node_pipeline("melody-trace-plan", {"score": score, "alignment": alignment, "gestureLibrary": gestures})
    sticker_selected = any(item.get("type") == "sticker_arrangement" for item in recipe.get("activities", []))
    arrangement_artifact = songs.get_artifact(preparation["songId"], "sticker-arrangement-plan.json")
    if sticker_selected and (not arrangement_artifact or arrangement_artifact.get("sourceScoreVerifiedAt") != score.get("verifiedAt")):
        raise CliError("ARRANGEMENT_INFERENCE_REQUIRED", "请先由 QwenWork 生成 Arrangement Plan，再运行 import-arrangement-plan。")
    raw_plan = arrangement_artifact.get("plan") if arrangement_artifact else None
    event_pack = generate_sticker_stem_plan(score, raw_plan=raw_plan)
    event_pack["totalBeats"] = event_pack["measureCount"] * (float(event_pack["meter"].get("beats", 4)) * 4 / float(event_pack["meter"].get("unit", 4)))
    event_pack["readinessMode"] = "QWENWORK_LOCAL_CLI_WEB_AUDIO_V2"
    songs.save_artifact(preparation["songId"], "listening-body-plan.json", listening)
    songs.save_artifact(preparation["songId"], "melody-trace-plan.json", trace)
    songs.save_artifact(preparation["songId"], "sticker-stems.json", event_pack)
    arrangement = default_sticker_arrangement(preparation, recipe)
    preparations.save_artifact(args.preparation_id, "sticker-arrangement.json", arrangement)
    preparations.update_preparation(args.preparation_id, {"readinessStatus": "NOT_EVALUATED", "status": "DRAFT"}, internal=True)
    return {"preparationId": args.preparation_id, "listeningBodyPlan": listening, "melodyTracePlan": trace, "arrangementEventPack": event_pack, "stickerArrangement": arrangement}


def command_readiness(args: argparse.Namespace) -> dict:
    songs, preparations = repositories()
    preparation = require_preparation(preparations, args.preparation_id)
    song_id = preparation["songId"]
    sampler = read_json(ROOT / "assets" / "web-sampler-v1" / "sample-library.json")
    payload = {
        "preparation": preparation,
        "song": require_song(songs, song_id),
        "verifiedScore": songs.get_verified_score(song_id),
        "materialMatch": songs.get_artifact(song_id, "material-match.json"),
        "learningProfile": songs.get_artifact(song_id, "learning-profile.json"),
        "lessonRecipe": preparations.get_artifact(args.preparation_id, "lesson-recipe.json"),
        "melodyTracePlan": songs.get_artifact(song_id, "melody-trace-plan.json"),
        "gestureLibrary": read_json(RUNTIME / "gestures" / "gesture-library.json"),
        "measureAlignment": songs.get_artifact(song_id, "measure-alignment.json"),
        "listeningBodyPlan": songs.get_artifact(song_id, "listening-body-plan.json"),
        "stickerStemPack": songs.get_artifact(song_id, "sticker-stems.json"),
        "webSampler": sampler,
    }
    readiness = node_pipeline("readiness", payload)
    readiness["updatedAt"] = utc_now()
    preparations.save_artifact(args.preparation_id, "readiness.json", readiness)
    preparations.update_preparation(args.preparation_id, {
        "readinessStatus": "CURRENT", "status": "READY" if readiness["ready"] else "DRAFT",
    }, internal=True)
    return {"preparationId": args.preparation_id, "readiness": readiness}


def command_export(args: argparse.Namespace) -> dict:
    _, preparations = repositories()
    preparation = require_preparation(preparations, args.preparation_id)
    readiness = preparations.get_artifact(args.preparation_id, "readiness.json")
    if preparation.get("status") != "READY" or not readiness or readiness.get("ready") is not True:
        raise CliError("NOT_READY", "只有通过最新 Readiness Gate 的备课才能导出。")
    from classroom.static_exporter.exporter import export_classroom
    return export_classroom(ROOT, args.preparation_id)


def bool_value(raw: str) -> bool:
    if str(raw).lower() in {"true", "1", "yes"}: return True
    if str(raw).lower() in {"false", "0", "no"}: return False
    raise argparse.ArgumentTypeError("必须是 true 或 false")


def build_parser() -> argparse.ArgumentParser:
    parser = JsonParser(prog="animal_band_cli.py")
    subs = parser.add_subparsers(dest="command", required=True, parser_class=JsonParser)
    subs.add_parser("doctor").set_defaults(handler=command_doctor)
    p = subs.add_parser("recognize-score"); p.add_argument("--score-image", required=True); p.add_argument("--audio", required=True); p.add_argument("--title", required=True); p.add_argument("--inference-input", required=True); p.set_defaults(handler=command_recognize)
    p = subs.add_parser("update-score"); p.add_argument("--song-id", required=True); p.add_argument("--score-json", required=True); p.set_defaults(handler=command_update_score)
    p = subs.add_parser("verify-score"); p.add_argument("--song-id", required=True); p.add_argument("--confirmed", required=True, type=bool_value); p.add_argument("--reviewer", default="teacher"); p.set_defaults(handler=command_verify_score)
    p = subs.add_parser("score-status"); p.add_argument("--song-id", required=True); p.set_defaults(handler=command_score_status)
    p = subs.add_parser("open-score-review"); p.add_argument("--song-id", required=True); p.add_argument("--idle-timeout", type=int, default=900); p.set_defaults(handler=command_open_score_review)
    p = subs.add_parser("analyze-song"); p.add_argument("--song-id", required=True); p.set_defaults(handler=command_analyze)
    p = subs.add_parser("generate-recipe"); p.add_argument("--song-id", required=True); p.add_argument("--activities", required=True); p.add_argument("--new", action="store_true"); p.set_defaults(handler=command_generate_recipe)
    p = subs.add_parser("confirm-recipe"); p.add_argument("--preparation-id", required=True); p.add_argument("--confirmed", required=True, type=bool_value); p.add_argument("--reviewer", default="teacher"); p.set_defaults(handler=command_confirm_recipe)
    p = subs.add_parser("set-measure-alignment"); p.add_argument("--preparation-id", required=True); p.add_argument("--start-measure", required=True, type=int); p.add_argument("--end-measure", required=True, type=int); p.add_argument("--start-sec", required=True, type=float); p.add_argument("--end-sec", required=True, type=float); p.set_defaults(handler=command_alignment)
    p = subs.add_parser("arrangement-context"); p.add_argument("--song-id", required=True); p.set_defaults(handler=command_arrangement_context)
    p = subs.add_parser("import-arrangement-plan"); p.add_argument("--song-id", required=True); p.add_argument("--plan-json", required=True); p.set_defaults(handler=command_import_arrangement)
    p = subs.add_parser("prepare-classroom"); p.add_argument("--preparation-id", required=True); p.set_defaults(handler=command_prepare)
    p = subs.add_parser("check-readiness"); p.add_argument("--preparation-id", required=True); p.set_defaults(handler=command_readiness)
    p = subs.add_parser("export-classroom"); p.add_argument("--preparation-id", required=True); p.set_defaults(handler=command_export)
    return parser


def main() -> int:
    command = None
    try:
        args = build_parser().parse_args()
        command = args.command
        data = args.handler(args)
        print(json.dumps({"ok": True, "command": command, "data": data}, ensure_ascii=False))
        return 0
    except CliError as error:
        print(json.dumps({"ok": False, "command": command, "error": {"code": error.code, "message": str(error)}}, ensure_ascii=False))
        return 1
    except Exception as error:
        print(json.dumps({"ok": False, "command": command, "error": {"code": "INTERNAL_ERROR", "message": str(error)}}, ensure_ascii=False))
        if os.environ.get("ANIMAL_BAND_DEBUG") == "1":
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
