#!/usr/bin/env python3
"""Short-lived, token-protected bridge for the Score Review UI."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import mimetypes
import os
from pathlib import Path
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
for candidate in (ROOT, RUNTIME, RUNTIME / "score_recognition"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from repositories.persistence_utils import utc_now  # noqa: E402
from repositories.preparation_repository import PreparationRepository  # noqa: E402
from repositories.song_repository import SongRepository  # noqa: E402
from workspace_paths import resolve_workspace  # noqa: E402

MAX_BODY = 4 * 1024 * 1024
SONG_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
WORKSPACE = resolve_workspace(ROOT)


def score_issues(score: dict) -> list[str]:
    """Return only blocking review issues.

    Measure duration mismatches are intentionally advisory: numbered scores may
    contain pickups, lead-ins, incomplete bars, or source-specific bar lengths.
    The UI still warns about them, but they must never block human confirmation.
    """
    issues = []
    if not (1 <= int(score.get("teachingConfig", {}).get("singingMeasuresPerUnit", 0)) <= 8):
        issues.append("请选择演唱教学每几小节一段。")
    issues.extend(
        str(item.get("message") or item.get("code"))
        for item in score.get("warnings", [])
        if item.get("severity") == "blocking" and item.get("code") != "MEASURE_DURATION_MISMATCH"
    )
    return list(dict.fromkeys(issues))


def measure_origin(score: dict | None) -> int | None:
    measures = sorted(
        (item for item in (score or {}).get("measures") or [] if isinstance(item.get("number"), (int, float))),
        key=lambda item: int(item["number"]),
    )
    if not measures:
        return None
    valid = {int(item["number"]) for item in measures}
    try:
        requested = int(((score or {}).get("measureOrigin") or {}).get("sourceMeasure"))
    except (TypeError, ValueError):
        requested = None
    return requested if requested in valid else int(measures[0]["number"])


def measure_structure_signature(score: dict | None) -> tuple[tuple[str, ...], ...]:
    """Stable signature for bar grouping, independent of beat recalculation.

    Moving the same notes across barlines changes the nested grouping and must
    invalidate any previously calibrated original-audio measure alignment.
    """
    return tuple(
        tuple(str(note.get("noteId") or "") for note in (measure.get("notes") or []))
        for measure in ((score or {}).get("measures") or [])
    )


def alignment_ready(score: dict, alignment: dict | None) -> bool:
    calibration = (alignment or {}).get("calibration") or {}
    origin = measure_origin(score)
    return bool(alignment and origin is not None
                and alignment.get("sourceScoreVerifiedAt") in {None, score.get("verifiedAt")}
                and int(calibration.get("startMeasure", 0)) == origin
                and int(calibration.get("endMeasure", 0)) >= int(calibration.get("startMeasure", 0))
                and float(calibration.get("startSec", -1)) >= 0
                and float(calibration.get("endSec", 0)) > float(calibration.get("startSec", 0)))


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, *, song_id: str, token: str, idle_timeout: int):
        super().__init__(address, handler)
        self.song_id = song_id
        self.token = token
        self.idle_timeout = idle_timeout
        self.last_activity = time.monotonic()
        self.stop_requested = False
        self.songs = SongRepository(WORKSPACE)
        self.preparations = PreparationRepository(WORKSPACE)


class Handler(BaseHTTPRequestHandler):
    server: ReviewServer

    def log_message(self, fmt: str, *args) -> None:
        if os.environ.get("ANIMAL_BAND_DEBUG") == "1":
            super().log_message(fmt, *args)

    def _url(self):
        from urllib.parse import parse_qs, urlsplit
        value = urlsplit(self.path)
        return value.path, parse_qs(value.query)

    def _authorized(self, query: dict) -> bool:
        query_token = query.get("token", [""])[0]
        return bool(query_token) and query_token == self.server.token

    def _json(self, status: int, data=None, error: str | None = None, code: str = "BRIDGE_ERROR") -> None:
        payload = {"ok": error is None}
        if error is None:
            payload["data"] = data
        else:
            payload["error"] = {"code": code, "message": error}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length < 0 or length > MAX_BODY:
            raise ValueError("请求内容过大。")
        value = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if not isinstance(value, dict):
            raise ValueError("请求内容必须是 JSON 对象。")
        return value

    def _song_id(self, query: dict) -> str:
        song_id = query.get("songId", [self.server.song_id])[0]
        if song_id != self.server.song_id or not SONG_ID.fullmatch(song_id):
            raise PermissionError("此 Review Session 不能访问其他歌曲。")
        if not self.server.songs.get_song_by_id(song_id):
            raise FileNotFoundError("歌曲不存在。")
        return song_id

    def _media(self, song_id: str, kind: str) -> None:
        song = self.server.songs.get_song_by_id(song_id)
        public = song.get("assets", {}).get(kind)
        if not public:
            raise FileNotFoundError("资源不存在。")
        relative = str(public).removeprefix("data/")
        song_root = (WORKSPACE / "songs" / song_id).resolve()
        path = (WORKSPACE / relative).resolve()
        if song_root not in path.parents or not path.is_file():
            raise PermissionError("资源路径无效。")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str) -> bool:
        roots = {"/review/score/": ROOT / "review" / "score", "/classroom/core/": ROOT / "classroom" / "core"}
        for prefix, root in roots.items():
            if not path.startswith(prefix):
                continue
            relative = path[len(prefix):]
            if not relative or relative == "review_shell.tmpl":
                return False
            target = (root / relative).resolve()
            if root.resolve() not in target.parents or not target.is_file():
                self.send_error(404)
                return True
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return True
        return False

    def do_HEAD(self) -> None:
        path, _query = self._url()
        if path == "/":
            self.server.last_activity = time.monotonic()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return
        self.send_response(404)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        path, query = self._url()
        if path == "/":
            self.server.last_activity = time.monotonic()
            template = (ROOT / "review" / "score" / "review_shell.tmpl").read_text(encoding="utf-8")
            session = json.dumps({
                "token": self.server.token,
                "songId": self.server.song_id,
                "mode": "teacher",
                "expiresInSec": int(self.server.idle_timeout),
            }, ensure_ascii=False).replace("</", "<\\/")
            bootstrap = (
                '<base href="/review/score/">\n'
                f'  <script>window.__ANIMAL_BAND_REVIEW_SESSION__ = Object.freeze({session});</script>'
            )
            html = template.replace("<head>", f"<head>\n  {bootstrap}", 1)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/review/score/":
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if self._static(path):
            return
        if not path.startswith("/bridge/") or not self._authorized(query):
            self._json(403, error="Review session token 无效。", code="TOKEN_REQUIRED")
            return
        self.server.last_activity = time.monotonic()
        try:
            song_id = self._song_id(query) if path != "/bridge/status" else self.server.song_id
            if path == "/bridge/status":
                self._json(200, {"running": True, "songId": song_id, "bindHost": self.server.server_address[0], "tokenProtected": True})
            elif path == "/bridge/resources":
                song = self.server.songs.get_song_by_id(song_id)
                assets = song.get("assets", {})
                self._json(200, {
                    "resourceMode": (song.get("metadata") or {}).get("resourceMode") or ("SCORE_AUDIO" if assets.get("originalAudio") else "SCORE_ONLY"),
                    "scoreImage": bool(assets.get("scoreImage")),
                    "originalAudio": bool(assets.get("originalAudio")),
                })
            elif path == "/bridge/score":
                self._json(200, {"score": self.server.songs.get_score(song_id)})
            elif path == "/bridge/measure-alignment":
                self._json(200, {"alignment": self.server.songs.get_artifact(song_id, "measure-alignment.json")})
            elif path == "/bridge/source-image":
                self._media(song_id, "scoreImage")
            elif path == "/bridge/original-audio":
                self._media(song_id, "originalAudio")
            else:
                self._json(404, error="Endpoint 不存在。", code="NOT_FOUND")
        except FileNotFoundError as error:
            self._json(404, error=str(error), code="NOT_FOUND")
        except PermissionError as error:
            self._json(403, error=str(error), code="FORBIDDEN")
        except Exception as error:
            self._json(400, error=str(error))

    def do_PUT(self) -> None:
        path, query = self._url()
        if not path.startswith("/bridge/") or not self._authorized(query):
            self._json(403, error="Review session token 无效。", code="TOKEN_REQUIRED")
            return
        self.server.last_activity = time.monotonic()
        try:
            song_id, value = self._song_id(query), self._body()
            if path.startswith("/bridge/score/"):
                previous_score = self.server.songs.get_score(song_id)
                previous_origin = measure_origin(previous_score)
                previous_structure = measure_structure_signature(previous_score)
                score = deepcopy(value)
                score["songId"] = song_id
                if path.endswith("/draft"):
                    score.update({"verificationStatus": "draft", "verifiedBy": None, "verifiedAt": None})
                    score.setdefault("source", {}).update({"humanReviewed": False, "reviewedAt": None})
                elif path.endswith("/reviewed"):
                    issues = score_issues(score)
                    if issues:
                        raise ValueError(" ".join(issues))
                    score.update({"verificationStatus": "reviewed", "verifiedBy": None, "verifiedAt": None})
                    score.setdefault("source", {}).update({"humanReviewed": True, "reviewedAt": utc_now()})
                elif path.endswith("/verified"):
                    current = self.server.songs.get_score(song_id)
                    if current.get("verificationStatus") != "reviewed":
                        raise ValueError("乐谱必须先标记为已审核。")
                    issues = score_issues(score)
                    if issues:
                        raise ValueError(" ".join(issues))
                    now = utc_now()
                    score.update({"verificationStatus": "verified", "verifiedBy": str(score.get("verifiedBy") or "teacher-review"), "verifiedAt": now})
                    score.setdefault("source", {}).update({"humanReviewed": True, "reviewedAt": now})
                else:
                    raise FileNotFoundError("Endpoint 不存在。")
                next_origin = measure_origin(score)
                next_structure = measure_structure_signature(score)
                structure_changed = previous_structure != next_structure
                self.server.songs.save_score(song_id, score)
                if previous_origin != next_origin or structure_changed:
                    self.server.songs.delete_artifact(song_id, "measure-alignment.json")
                self.server.preparations.invalidate_for_song(song_id)
                self._json(200, {
                    "score": score,
                    "measureOriginChanged": previous_origin != next_origin,
                    "measureStructureChanged": structure_changed,
                })
                return
            if path == "/bridge/measure-alignment":
                song = self.server.songs.get_song_by_id(song_id)
                if not song.get("assets", {}).get("originalAudio"):
                    raise ValueError("当前为简谱模式，不需要原曲小节校准。")
                score = self.server.songs.get_score(song_id)
                calibration = value.get("calibration")
                if not calibration:
                    raise ValueError("请先标记校准开始和结束。")
                alignment = {**value, "schemaVersion": "2.0.0", "songId": song_id, "sourceScoreVerifiedAt": score.get("verifiedAt"), "updatedAt": utc_now(), "calibrationStatus": "teacher_verified"}
                if not alignment_ready(score, alignment):
                    origin = measure_origin(score)
                    raise ValueError(f"Measure Alignment 无效。请从教学第1小节（谱面第 {origin} 小节）开始校准。")
                self.server.songs.save_artifact(song_id, "measure-alignment.json", alignment)
                self.server.preparations.invalidate_readiness_for_song(song_id)
                self._json(200, {"alignment": alignment})
                return
            raise FileNotFoundError("Endpoint 不存在。")
        except FileNotFoundError as error:
            self._json(404, error=str(error), code="NOT_FOUND")
        except PermissionError as error:
            self._json(403, error=str(error), code="FORBIDDEN")
        except Exception as error:
            self._json(400, error=str(error), code="VALIDATION_ERROR")

    def do_POST(self) -> None:
        path, query = self._url()
        if not path.startswith("/bridge/") or not self._authorized(query):
            self._json(403, error="Review session token 无效。", code="TOKEN_REQUIRED")
            return
        self.server.last_activity = time.monotonic()
        try:
            if path == "/bridge/close":
                self.server.stop_requested = True
                self._json(200, {"closed": True})
                return
            raise FileNotFoundError("Endpoint 不存在。")
        except FileNotFoundError as error:
            self._json(404, error=str(error), code="NOT_FOUND")
        except Exception as error:
            self._json(400, error=str(error), code="BRIDGE_OPERATION_FAILED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--song-id", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--port-file", required=True, type=Path)
    parser.add_argument("--idle-timeout", type=int, default=900)
    parser.add_argument("--host", default="0.0.0.0", choices=("0.0.0.0", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    if not SONG_ID.fullmatch(args.song_id) or not (WORKSPACE / "songs" / args.song_id / "song.json").is_file():
        return 2
    if len(args.token) < 32:
        return 2
    server = ReviewServer((args.host, args.port), Handler, song_id=args.song_id, token=args.token, idle_timeout=max(30, min(3600, args.idle_timeout)))
    server.timeout = 1
    args.port_file.write_text(json.dumps({"port": server.server_port, "pid": os.getpid()}), encoding="utf-8")
    try:
        while not server.stop_requested and time.monotonic() - server.last_activity < server.idle_timeout:
            server.handle_request()
    finally:
        server.server_close()
        args.port_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
