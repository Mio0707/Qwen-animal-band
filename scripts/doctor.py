#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--json", action="store_true"); args = parser.parse_args()
    python_ok = sys.version_info >= (3, 9)
    configured_node = str(os.environ.get("ANIMAL_BAND_NODE") or "").strip()
    node_path = configured_node if configured_node and Path(configured_node).is_file() else shutil.which("node")
    node_version = None
    if node_path:
        node_version = subprocess.run([node_path, "--version"], text=True, capture_output=True).stdout.strip()
    engine_files = [ROOT / "runtime" / "animal_band_cli.py", ROOT / "runtime" / "engine" / "pipeline-cli.js"]
    sampler_path = ROOT / "assets" / "web-sampler-v1" / "sample-library.json"
    classroom_files = [ROOT / "classroom" / "app" / "classroom" / "index.html", ROOT / "classroom" / "web_audio" / "track_mixer.js"]
    review_files = [ROOT / "review" / "score" / "index.html", ROOT / "review" / "score" / "score_review.js", ROOT / "runtime" / "review_bridge.py"]
    workspace_dirs = [ROOT / "workspace" / name for name in ("songs", "preparations", "exports")]
    sampler_count = 0
    sampler_ok = False
    try:
        library = json.loads(sampler_path.read_text(encoding="utf-8"))
        sampler_count = sum(len(item.get("samples", [])) for item in library.get("instruments", {}).values())
        sampler_ok = sampler_count == 31 and all((sampler_path.parent / sample["path"]).is_file() for item in library["instruments"].values() for sample in item["samples"])
    except Exception:
        pass
    status = {
        "ready": python_ok and bool(node_path) and all(path.is_file() for path in engine_files) and sampler_ok and all(path.is_file() for path in classroom_files) and all(path.is_file() for path in review_files) and all(path.is_dir() for path in workspace_dirs),
        "python": {"ok": python_ok, "version": sys.version.split()[0], "executable": sys.executable},
        "node": {"ok": bool(node_path), "version": node_version, "executable": node_path},
        "inference": {"ok": True, "layer": "qwenwork_skill", "runtimeNetworkCalls": False, "apiKeyRequired": False},
        "engine": {"ok": all(path.is_file() for path in engine_files)},
        "sampler": {"ok": sampler_ok, "sampleCount": sampler_count, "path": "assets/web-sampler-v1/sample-library.json"},
        "classroom": {"ok": all(path.is_file() for path in classroom_files)},
        "review": {"ok": all(path.is_file() for path in review_files), "bridge": "loopback_short_lived"},
        "workspace": {"ok": all(path.is_dir() for path in workspace_dirs)},
    }
    if args.json:
        print(json.dumps(status, ensure_ascii=False))
    else:
        print("Animal Band 环境：" + ("READY" if status["ready"] else "NOT READY"))
        for key in ("python", "node", "inference", "engine", "sampler", "classroom", "review", "workspace"):
            print(f"- {key}: {json.dumps(status[key], ensure_ascii=False)}")
    return 0 if status["ready"] else 1


if __name__ == "__main__": raise SystemExit(main())
