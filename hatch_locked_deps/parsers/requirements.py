from __future__ import annotations

import re
from typing import TYPE_CHECKING

from hatch_locked_deps.parsers.dep import Dependency


if TYPE_CHECKING:
    from pathlib import Path


def parse_requirements_txt(path: Path) -> list[Dependency]:
    """Parse pip-compile / pip-tools output.

    Strips hashes but preserves environment markers.
    """
    deps = []
    for raw_line in path.read_text().splitlines():
        stripped = raw_line.split("#")[0].split("\\")[0].strip()
        if not stripped or stripped.startswith("-"):
            continue
        # Strip hashes but keep markers
        cleaned = re.sub(r"\s*--hash=\S+", "", stripped).strip()
        match = re.match(
            r"^([a-zA-Z0-9_.-]+(?:\[[a-zA-Z0-9_,.-]+\])?==\S+?)(\s*;.*)?$",
            cleaned,
        )
        if not match:
            msg = f"Invalid requirements.txt line: {cleaned}"
            raise ValueError(msg)
        name_version = match[1]
        markers = match[2].strip().lstrip("; ").strip() if match[2] else None
        name, version = name_version.split("==")
        deps.append(Dependency(name=name, version=version, markers=markers))
    return deps
