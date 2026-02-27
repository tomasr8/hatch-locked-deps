from __future__ import annotations

import re
import tomllib
from typing import TYPE_CHECKING

from hatch_locked_deps.parsers.dep import Dependency


if TYPE_CHECKING:
    from pathlib import Path

# Regex to detect `extra == "..."` or `extra == '...'` in a marker
_EXTRA_MARKER_RE = re.compile(
    r"""extra\s*==\s*["']([^"']+)["']""",
)


def parse_pylock_toml(
    path: Path,
    *,
    include_extras: list[str] | None = None,
) -> list[Dependency]:
    """Parse PEP 751 pylock.toml.

    By default, packages with `extra == "..."` markers are excluded.
    Use include_extras to include specific extras.
    """
    data = tomllib.loads(path.read_text())
    extras_set = set(include_extras or [])
    deps = []

    for pkg in data.get("packages", []):
        marker = pkg.get("marker")
        extra_match = _EXTRA_MARKER_RE.search(marker) if marker else None

        if extra_match:
            extra_name = extra_match.group(1)
            if extra_name not in extras_set:
                continue

        deps.append(
            Dependency(
                name=pkg["name"],
                version=pkg["version"],
                markers=marker,
            )
        )

    return deps
