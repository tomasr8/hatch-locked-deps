from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.plugin import hookimpl

from hatch_locked_deps.formats import Format
from hatch_locked_deps.parsers import PARSERS, auto_detect


class LockedDepsBuildHook(BuildHookInterface):
    PLUGIN_NAME = "locked-deps"

    def initialize(self, version, build_data):  # noqa: ARG002
        root = Path(self.root)
        lock_file = self.config.get("lock-file")
        exclude = {n.lower() for n in self.config.get("exclude", [])}
        include_extras = self.config.get("include-extras")

        if lock_file:
            path = root / lock_file
            fmt = Format(self.config["format"]) if self.config.get("format") else infer_format(path)
        else:
            fmt, path = auto_detect(root)

        # Build parser kwargs based on format
        kwargs = {}
        if fmt in {Format.PYLOCK, Format.UV} and include_extras:
            kwargs["include_extras"] = include_extras
        if fmt == Format.UV:
            kwargs["project_name"] = self.metadata.name

        deps = PARSERS[fmt](path, **kwargs)

        # Filter out the project itself and any explicit exclusions
        project_name = self.metadata.name.lower()
        deps = [d for d in deps if d.name.lower() not in {project_name} | exclude]

        build_data["dependencies"] = [str(d) for d in deps]


def infer_format(path: Path) -> Format:
    name = path.name
    if name == "requirements.txt":
        return Format.REQUIREMENTS
    if name == "uv.lock":
        return Format.UV
    if name == "pylock.toml":
        return Format.PYLOCK
    msg = f"Cannot infer format for '{name}'. Set 'format' in [tool.hatch.build.hooks.locked-deps]"
    raise ValueError(msg)


@hookimpl
def hatch_register_build_hook():
    return LockedDepsBuildHook
