#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "runtime") not in sys.path:
    sys.path.insert(0, str(ROOT / "runtime"))

from node_runtime import resolve_node  # noqa: E402
from workspace_paths import resolve_workspace  # noqa: E402
from score_recognition.recognition_plan import pillow_available  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--json", action="store_true"); args = parser.parse_args()
    python_ok = sys.version_info >= (3, 9)
    node_path = resolve_node()
    node_version = None
    if node_path:
        node_version = subprocess.run([node_path, "--version"], text=True, capture_output=True).stdout.strip()
    engine_files = [ROOT / "runtime" / "animal_band_cli.py", ROOT / "runtime" / "engine" / "pipeline-cli.js"]
    recognition_files = [
        ROOT / "runtime" / "score_recognition" / "recognition_plan.py",
        ROOT / "runtime" / "score_recognition" / "inference_assembler.py",
        ROOT / "runtime" / "score_recognition" / "score_normalizer.py",
    ]
    sampler_path = ROOT / "assets" / "web-sampler-v1" / "sample-library.json"
    classroom_files = [ROOT / "classroom" / "app" / "classroom" / "index.html", ROOT / "classroom" / "web_audio" / "track_mixer.js"]
    review_files = [ROOT / "review" / "score" / "review_shell.tmpl", ROOT / "review" / "score" / "score_review.js", ROOT / "runtime" / "review_bridge.py"]
    try:
        workspace_root = resolve_workspace(ROOT)
        workspace_dirs = [workspace_root / name for name in ("songs", "preparations", "exports", "recognition-prep-v3")]
        for path in workspace_dirs:
            path.mkdir(parents=True, exist_ok=True)
        workspace_writable = True
    except Exception:
        workspace_root = ROOT / "workspace"
        workspace_dirs = [workspace_root / name for name in ("songs", "preparations", "exports", "recognition-prep-v3")]
        workspace_writable = False
    sampler_count = 0
    sampler_ok = False
    try:
        library = json.loads(sampler_path.read_text(encoding="utf-8"))
        sampler_count = sum(len(item.get("samples", [])) for item in library.get("instruments", {}).values())
        sampler_ok = sampler_count == 31 and all((sampler_path.parent / sample["path"]).is_file() for item in library["instruments"].values() for sample in item["samples"])
    except Exception:
        pass
    status = {
        "ready": python_ok and bool(node_path) and all(path.is_file() for path in engine_files) and all(path.is_file() for path in recognition_files) and sampler_ok and all(path.is_file() for path in classroom_files) and all(path.is_file() for path in review_files) and workspace_writable and all(path.is_dir() for path in workspace_dirs),
        "python": {"ok": python_ok, "version": sys.version.split()[0], "executable": sys.executable},
        "node": {"ok": bool(node_path), "version": node_version, "executable": node_path, "autoDiscovered": bool(node_path)},
        "inference": {"ok": True, "layer": "qwenwork_skill", "runtimeNetworkCalls": False, "apiKeyRequired": False},
        "recognitionV3": {"ok": all(path.is_file() for path in recognition_files), "pillowAvailable": pillow_available(), "fallback": "whole_page_if_pillow_missing", "perRegionAssembly": True},
        "engine": {"ok": all(path.is_file() for path in engine_files)},
        "sampler": {"ok": sampler_ok, "sampleCount": sampler_count, "path": "assets/web-sampler-v1/sample-library.json"},
        "classroom": {"ok": all(path.is_file() for path in classroom_files)},
        "review": {"ok": all(path.is_file() for path in review_files), "bridge": "root_html_bootstrap_token_no_cookie"},
        "workspace": {"ok": workspace_writable and all(path.is_dir() for path in workspace_dirs), "path": str(workspace_root), "writable": workspace_writable},
    }
    if args.json:
        print(json.dumps(status, ensure_ascii=False))
    else:
        print("Animal Band 环境：" + ("READY" if status["ready"] else "NOT READY"))
        for key in ("python", "node", "inference", "recognitionV3", "engine", "sampler", "classroom", "review", "workspace"):
            print(f"- {key}: {json.dumps(status[key], ensure_ascii=False)}")
    return 0 if status["ready"] else 1


if __name__ == "__main__": raise SystemExit(main())
