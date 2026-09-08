"""Freeze a READY preparation into a serverless static classroom."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from repositories.persistence_utils import read_json
from repositories.preparation_repository import PreparationRepository
from repositories.song_repository import SongRepository


def _copy_tree(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _session(root: Path, preparation_id: str) -> tuple[dict, dict, dict]:
    songs, preparations = SongRepository(root / "workspace"), PreparationRepository(root / "workspace")
    preparation = preparations.get_preparation_by_id(preparation_id)
    if not preparation:
        raise KeyError(preparation_id)
    song_id = preparation["songId"]
    song = songs.get_song_by_id(song_id)
    if not song:
        raise RuntimeError("歌曲不存在。")
    session = {
        "offline": True,
        "packSchemaVersion": "2.0.0",
        "songs": [song],
        "preparations": [preparation],
        "lessonRecipes": {preparation_id: preparations.get_artifact(preparation_id, "lesson-recipe.json")},
        "verifiedScores": {song_id: songs.get_verified_score(song_id)},
        "readiness": {preparation_id: preparations.get_artifact(preparation_id, "readiness.json")},
        "melodyTracePlans": {song_id: songs.get_artifact(song_id, "melody-trace-plan.json")},
        "measureAlignments": {song_id: songs.get_artifact(song_id, "measure-alignment.json")},
        "listeningBodyPlans": {song_id: songs.get_artifact(song_id, "listening-body-plan.json")},
        "stickerStemPacks": {song_id: songs.get_artifact(song_id, "sticker-stems.json")},
        "arrangementEventPacks": {song_id: songs.get_artifact(song_id, "sticker-stems.json")},
        "stickerArrangements": {preparation_id: preparations.get_artifact(preparation_id, "sticker-arrangement.json")},
        "gestureLibrary": read_json(root / "runtime" / "gestures" / "gesture-library.json"),
        "solfegeSampleLibrary": read_json(root / "classroom" / "assets" / "audio" / "solfege" / "voice-katy" / "sample-library.json"),
        "rhythmConfig": {
            "teachingAssets": read_json(root / "runtime" / "teaching_assets" / "stage1-teaching-assets.json"),
            "actionMap": read_json(root / "runtime" / "runtime_data" / "rhythm" / "rhythm-action-map.json"),
            "manifest": read_json(root / "runtime" / "runtime_data" / "rhythm" / "rhythm-performer-manifest.json"),
            "policy": read_json(root / "runtime" / "runtime_data" / "rhythm" / "rhythm-runtime-policy.json"),
            "noteSoundMap": read_json(root / "runtime" / "runtime_data" / "rhythm" / "rhythm-note-sound-map.json"),
        },
    }
    return session, preparation, song


def export_classroom(root: Path, preparation_id: str) -> dict:
    root = Path(root).resolve()
    session, preparation, song = _session(root, preparation_id)
    exports = root / "workspace" / "exports"
    destination = exports / preparation_id
    destination.mkdir(parents=True, exist_ok=True)
    _copy_tree(root / "classroom" / "app", destination / "app")
    _copy_tree(root / "classroom" / "core", destination / "core")
    _copy_tree(root / "classroom" / "assets", destination / "assets")
    _copy_tree(root / "classroom" / "data", destination / "data")
    _copy_tree(root / "classroom" / "web_audio", destination / "web_audio")
    _copy_tree(root / "assets" / "web-sampler-v1", destination / "assets" / "web-sampler-v1")
    _copy_tree(root / "workspace" / "songs" / preparation["songId"], destination / "data" / "songs" / preparation["songId"])
    preparation_file = root / "workspace" / "preparations" / f"{preparation_id}.json"
    (destination / "data" / "preparations").mkdir(parents=True, exist_ok=True)
    shutil.copy2(preparation_file, destination / "data" / "preparations" / preparation_file.name)
    _copy_tree(root / "workspace" / "preparations" / preparation_id, destination / "data" / "preparations" / preparation_id)
    _json(destination / "offline" / "session.json", session)
    entrypoint = f"app/classroom/?preparation={preparation_id}&mode=live&offline=1"
    (destination / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        f"<title>{song.get('title', 'Animal Band')}</title><script>location.replace('{entrypoint}')</script>"
        f"<p><a href='{entrypoint}'>进入 Animal Band 课堂</a></p>", encoding="utf-8")
    files = sorted(path for path in destination.rglob("*") if path.is_file())
    manifest = {
        "schemaVersion": "2.0.0", "preparationId": preparation_id, "songId": preparation["songId"],
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "entrypoint": entrypoint,
        "readinessMode": "QWENWORK_LOCAL_CLI_WEB_AUDIO_V2", "fileCount": len(files),
        "files": [{"path": path.relative_to(destination).as_posix(), "size": path.stat().st_size} for path in files],
    }
    _json(destination / "offline" / "manifest.json", manifest)
    zip_path = exports / f"animal-band-classroom-{preparation_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(item for item in destination.rglob("*") if item.is_file()):
            bundle.write(path, path.relative_to(destination).as_posix())
    return {
        "preparationId": preparation_id, "directory": str(destination), "zip": str(zip_path),
        "entrypoint": entrypoint, "previewCommand": f"cd {json.dumps(str(destination))} && python3 -m http.server 4176",
        "sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(), "fileCount": len(manifest["files"]),
    }
