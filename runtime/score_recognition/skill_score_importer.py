"""Import and normalize structured score inference produced by QwenWork."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from score_normalizer import normalize_score

DEFAULT_MODEL = "qwenwork-native"


def run_recognition(
    image_path: Path,
    song_id: str,
    output_root: Path,
    *,
    title: str | None = None,
    metadata: dict | None = None,
    model: str = DEFAULT_MODEL,
    raw_input: Path | None = None,
) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", song_id):
        raise ValueError("songId 只能包含字母、数字、下划线和连字符。")
    if not image_path.is_file():
        raise ValueError(f"简谱图片不存在：{image_path}")

    song_dir = output_root / song_id
    source_dir = song_dir / "source"
    recognition_dir = song_dir / "recognition"
    source_dir.mkdir(parents=True, exist_ok=True)
    recognition_dir.mkdir(parents=True, exist_ok=True)
    stored_image = source_dir / f"score-image{image_path.suffix.lower()}"
    if image_path.resolve() != stored_image.resolve():
        shutil.copyfile(image_path, stored_image)

    if not raw_input:
        raise ValueError("识谱推理必须由 QwenWork 完成，并通过 inference input 传入结构化 JSON。")
    raw = json.loads(raw_input.read_text(encoding="utf-8"))
    raw_path = recognition_dir / "raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    normalized = normalize_score(
        raw,
        song_id,
        "recognition/raw.json",
        title=title,
        model=model,
        recognized_at=timestamp,
        metadata=metadata,
    )
    normalized_path = recognition_dir / "normalized.json"
    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Import QwenWork numbered-score inference as a draft.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--song-id", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--title")
    parser.add_argument("--metadata-json")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--inference-input", required=True, type=Path, help="Structured JSON produced by QwenWork.")
    args = parser.parse_args()
    metadata = json.loads(args.metadata_json) if args.metadata_json else None
    normalized = run_recognition(
        args.image, args.song_id, args.output_root, title=args.title,
        metadata=metadata, model=args.model, raw_input=args.inference_input,
    )
    print(json.dumps({
        "songId": normalized["songId"],
        "verificationStatus": normalized["verificationStatus"],
        "output": str((args.output_root / args.song_id).resolve()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
