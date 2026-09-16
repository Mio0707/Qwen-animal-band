"""Import and normalize structured score inference produced by QwenWork.

Recognition Pipeline v3 accepts either:
- a preferred directory of independent region JSON files; or
- the legacy single aggregate JSON file.
The repository, not the model, performs assembly and source-coverage validation.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from .inference_assembler import assemble_inference
    from .score_normalizer import normalize_score
except ImportError:  # direct-script compatibility
    from inference_assembler import assemble_inference
    from score_normalizer import normalize_score

DEFAULT_MODEL = "qwenwork-native"


def run_recognition(image_path: Path, song_id: str, output_root: Path, *, title: str | None = None, metadata: dict | None = None, model: str = DEFAULT_MODEL, raw_input: Path | None = None, inference_dir: Path | None = None, recognition_plan: Path | None = None, raw_candidate: dict | None = None, preflight_report: dict | None = None) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", song_id):
        raise ValueError("songId 只能包含字母、数字、下划线和连字符。")
    if not image_path.is_file():
        raise ValueError(f"简谱图片不存在：{image_path}")
    if not recognition_plan:
        raise ValueError("Recognition v3 必须提供 recognition plan。")
    recognition_plan = Path(recognition_plan).expanduser().resolve()
    if not recognition_plan.is_file():
        raise ValueError(f"recognition plan 不存在：{recognition_plan}")
    plan = json.loads(recognition_plan.read_text(encoding="utf-8"))
    if raw_candidate is None:
        raw, report = assemble_inference(plan, inference_input=raw_input, inference_dir=inference_dir)
    else:
        raw = raw_candidate
        report = preflight_report or {"ok": True}
    song_dir = output_root / song_id
    source_dir = song_dir / "source"
    recognition_dir = song_dir / "recognition"
    source_dir.mkdir(parents=True, exist_ok=True)
    recognition_dir.mkdir(parents=True, exist_ok=True)
    stored_image = source_dir / f"score-image{image_path.suffix.lower()}"
    if image_path.resolve() != stored_image.resolve():
        shutil.copyfile(image_path, stored_image)
    (recognition_dir / "recognition-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (recognition_dir / "preflight-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raw_path = recognition_dir / "raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    recognition_metadata = dict(metadata or {})
    recognition_metadata["recognitionV3"] = {
        "planId": plan.get("planId"), "strategy": plan.get("strategy"), "profile": plan.get("profile"),
        "layoutConfidence": plan.get("layoutConfidence"), "complexity": plan.get("complexity"),
        "expectedSystems": (plan.get("coverage") or {}).get("expectedSystems"),
        "coverageValidated": bool(report.get("ok")), "measureCount": report.get("measureCount"),
        "systemCount": report.get("systemCount"), "advisoryCount": len(report.get("advisories") or []),
    }
    normalized = normalize_score(raw, song_id, "recognition/raw.json", title=title, model=model, recognized_at=timestamp, metadata=recognition_metadata)
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
    parser.add_argument("--inference-input", type=Path, help="Legacy aggregate JSON produced by QwenWork.")
    parser.add_argument("--inference-dir", type=Path, help="Recognition v3 directory containing region JSON files.")
    parser.add_argument("--recognition-plan", required=True, type=Path)
    args = parser.parse_args()
    if bool(args.inference_input) == bool(args.inference_dir):
        parser.error("exactly one of --inference-input or --inference-dir is required")
    metadata = json.loads(args.metadata_json) if args.metadata_json else None
    normalized = run_recognition(args.image, args.song_id, args.output_root, title=args.title, metadata=metadata, model=args.model, raw_input=args.inference_input, inference_dir=args.inference_dir, recognition_plan=args.recognition_plan)
    print(json.dumps({"songId": normalized["songId"], "verificationStatus": normalized["verificationStatus"], "output": str((args.output_root / args.song_id).resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
