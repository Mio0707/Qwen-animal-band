#!/usr/bin/env python3
"""Desktop-safe launcher for the Animal Band JSON CLI.

QwenWork/Desktop apps may not inherit the user's interactive shell PATH. This
launcher resolves Node.js from common install locations, exports
ANIMAL_BAND_NODE for the child process, and then delegates to the canonical
runtime/animal_band_cli.py entrypoint without changing its JSON protocol.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
CLI = RUNTIME / "animal_band_cli.py"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from node_runtime import resolve_node  # noqa: E402


def main() -> int:
    env = os.environ.copy()
    node = resolve_node()
    if node:
        env["ANIMAL_BAND_NODE"] = node
    result = subprocess.run(
        [sys.executable, str(CLI), *sys.argv[1:]],
        cwd=ROOT,
        env=env,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
