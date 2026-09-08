#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    for name in ("songs", "preparations", "exports"):
        target = ROOT / "workspace" / name
        target.mkdir(parents=True, exist_ok=True)
        (target / ".gitkeep").touch(exist_ok=True)
    doctor = subprocess.run([sys.executable, str(ROOT / "scripts" / "doctor.py"), "--json"], text=True, capture_output=True, cwd=ROOT)
    status = json.loads(doctor.stdout)
    if not status["ready"]:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        print("Animal Band 初始化失败，请修复上面的结构或运行时问题。", file=sys.stderr)
        return 1
    env = os.environ.copy()
    node = status.get("node", {}).get("executable")
    if node:
        env["ANIMAL_BAND_NODE"] = str(node)
    smoke = subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke_test.py")], cwd=ROOT, env=env)
    if smoke.returncode != 0:
        return smoke.returncode
    print("ANIMAL_BAND_READY")
    return 0


if __name__ == "__main__": raise SystemExit(main())
