from __future__ import annotations

import os
from pathlib import Path
import tempfile


def _probe_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".animal-band-write-test-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def resolve_workspace(root: Path) -> Path:
    """Resolve a stable writable workspace without mutating the installed Skill tree.

    Preference order:
    1. ANIMAL_BAND_WORKSPACE, when explicitly provided.
    2. Repository workspace, when writable (desktop/source checkout compatibility).
    3. User state directory ~/.animal-band-qwenwork/workspace.
    4. Process temp directory as a last resort.
    """
    root = Path(root).resolve()
    override = os.environ.get("ANIMAL_BAND_WORKSPACE")
    if override:
        target = Path(override).expanduser().resolve()
        if not _probe_writable(target):
            raise PermissionError(f"ANIMAL_BAND_WORKSPACE 不可写：{target}")
        return target

    repository_workspace = root / "workspace"
    if _probe_writable(repository_workspace):
        return repository_workspace

    home = Path.home()
    user_workspace = home / ".animal-band-qwenwork" / "workspace"
    if _probe_writable(user_workspace):
        return user_workspace

    temp_workspace = Path(tempfile.gettempdir()) / "animal-band-qwenwork" / "workspace"
    if _probe_writable(temp_workspace):
        return temp_workspace

    raise PermissionError("找不到可写的 Animal Band workspace。")
