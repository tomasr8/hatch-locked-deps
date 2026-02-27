from enum import StrEnum


class Format(StrEnum):
    PYLOCK = "pylock"
    UV = "uv"
    REQUIREMENTS = "requirements"


FILENAMES = {
    Format.PYLOCK: "pylock.toml",
    Format.UV: "uv.lock",
    Format.REQUIREMENTS: "requirements.txt",
}
