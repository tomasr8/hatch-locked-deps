from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from hatch_locked_deps.parsers.dep import Dependency


if TYPE_CHECKING:
    from pathlib import Path


def parse_uv_lock(
    path: Path,
    *,
    project_name: str,
    include_extras: list[str] | None = None,
) -> list[Dependency]:
    """Parse uv.lock with dependency graph walking.

    Only includes packages reachable from the root project's main
    dependencies. Packages only reachable via dev-dependencies are
    excluded. Optional dependencies (extras) are included only if
    explicitly requested via include_extras.
    """
    data = tomllib.loads(path.read_text())
    packages = data.get("package", [])

    # Index: name -> [package entries]
    pkg_index: dict[str, list[dict]] = {}
    for pkg in packages:
        pkg_index.setdefault(pkg["name"], []).append(pkg)

    # Find root package
    root = find_root(packages, project_name)

    # Walk main dependencies
    main_direct = {d["name"] for d in root.get("dependencies", [])}
    reachable_main = walk_deps(main_direct, pkg_index)

    deps = collect_deps(reachable_main, pkg_index)

    # Walk extras
    if include_extras:
        opt_deps = root.get("optional-dependencies", {})
        for extra in include_extras:
            extra_direct = {d["name"] for d in opt_deps.get(extra, [])}
            reachable_extra = walk_deps(extra_direct, pkg_index)
            # Only packages not already covered by main
            extra_only = reachable_extra - reachable_main
            deps.extend(collect_deps(extra_only, pkg_index, extra=extra))

    return deps


def find_root(packages: list[dict], project_name: str) -> dict:
    """Find the root/workspace package in the lockfile."""
    for pkg in packages:
        if pkg["name"] == project_name:
            return pkg
    msg = f"Root package '{project_name}' not found in uv.lock"
    raise ValueError(msg)


def walk_deps(seed_names: set[str], pkg_index: dict[str, list[dict]]) -> set[str]:
    """BFS to collect all transitively reachable package names."""
    visited: set[str] = set()
    queue = list(seed_names)

    while queue:
        name = queue.pop()
        if name in visited:
            continue
        visited.add(name)

        for entry in pkg_index.get(name, []):
            for dep in entry.get("dependencies", []):
                dep_name = dep["name"]
                if dep_name not in visited:
                    queue.append(dep_name)

    return visited


def collect_deps(
    names: set[str],
    pkg_index: dict[str, list[dict]],
    *,
    extra: str | None = None,
) -> list[Dependency]:
    """Build Dependency objects for a set of package names."""
    deps = []
    for name in sorted(names):
        for entry in pkg_index.get(name, []):
            if not entry.get("source", {}).get("registry"):
                continue

            resolution_marker = entry.get("resolution-marker")

            if extra and resolution_marker:
                markers = f'extra == "{extra}" and {resolution_marker}'
            elif extra:
                markers = f'extra == "{extra}"'
            elif resolution_marker:
                markers = resolution_marker
            else:
                markers = None

            deps.append(
                Dependency(
                    name=entry["name"],
                    version=entry["version"],
                    markers=markers,
                ),
            )
    return deps
