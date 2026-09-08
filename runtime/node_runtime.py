from __future__ import annotations

import os
from pathlib import Path
import shutil


def _candidate_paths() -> list[Path]:
    home = Path.home()
    candidates: list[Path] = []

    configured = str(os.environ.get("ANIMAL_BAND_NODE") or "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())

    path_node = shutil.which("node")
    if path_node:
        candidates.append(Path(path_node))

    candidates.extend([
        Path("/opt/homebrew/bin/node"),
        Path("/usr/local/bin/node"),
        Path("/usr/bin/node"),
        home / ".volta" / "bin" / "node",
        home / ".asdf" / "shims" / "node",
    ])

    candidates.extend(sorted((home / ".nvm" / "versions" / "node").glob("*/bin/node"), reverse=True))
    candidates.extend(sorted((home / ".local" / "share" / "fnm" / "node-versions").glob("*/installation/bin/node"), reverse=True))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = str(candidate)
        if value in seen:
            continue
        seen.add(value)
        unique.append(candidate)
    return unique


def resolve_node() -> str | None:
    """Resolve Node.js even when a GUI host did not inherit the shell PATH."""
    for candidate in _candidate_paths():
        try:
            path = candidate.expanduser().resolve()
        except OSError:
            continue
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None
