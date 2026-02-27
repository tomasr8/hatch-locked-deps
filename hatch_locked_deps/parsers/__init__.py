from __future__ import annotations

from typing import TYPE_CHECKING

from hatch_locked_deps.formats import FILENAMES, Format


if TYPE_CHECKING:
    from pathlib import Path

from hatch_locked_deps.parsers.pylock import parse_pylock_toml
from hatch_locked_deps.parsers.requirements import parse_requirements_txt
from hatch_locked_deps.parsers.uv import parse_uv_lock


PARSERS = {
    Format.PYLOCK: parse_pylock_toml,
    Format.UV: parse_uv_lock,
    Format.REQUIREMENTS: parse_requirements_txt,
}


def auto_detect(root: Path) -> tuple[Format, Path]:
    """Auto-detect lock file, preferring pylock.toml > uv.lock > requirements.txt."""
    for fmt, filename in FILENAMES.items():
        path = root / filename
        if path.exists():
            return fmt, path
    msg = f"No lock file found in {root}. Expected one of: {', '.join(FILENAMES.values())}"
    raise FileNotFoundError(msg)
