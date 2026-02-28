# hatch-locked-deps

A [Hatch](https://hatch.pypa.io/) build hook that pins your wheel's dependencies to the exact versions from your lock file, including all transitive dependencies.

## Why you should use this

When you install a Python wheel, pip resolves transitive dependencies to whatever versions it sees fit. This is fine for libraries, but for **end-user applications** you want reproducible installs with the exact same dependencies in development, CI and production.

`hatch-locked-deps` reads your lock file at build time and writes every resolved package (with pinned `==` versions) into your wheel's `Requires-Dist` metadata. This ensures that when you install the wheel, the dependencies are the same ones you have in your lock file.

## Supported lock file formats

| Format | File | Notes |
|---|---|---|
| [PEP 751](https://peps.python.org/pep-0751/) | `pylock.toml` | Preferred; standard lock file format |
| [uv](https://docs.astral.sh/uv/) | `uv.lock` | Full dependency graph walk; dev deps excluded automatically |
| [pip-compile](https://pip-tools.readthedocs.io/) | `requirements.txt` | Hashes stripped, markers preserved |

Auto-detection checks for these files in the order listed above.

## Quick start

Add `hatch-locked-deps` as a build dependency and enable the hook:

```toml
[build-system]
requires = ["hatchling", "hatch-locked-deps"]
build-backend = "hatchling.build"

[tool.hatch.build.hooks.locked-deps]
```

That's it. Your wheel metadata now define the exact same dependencies as your lock file.

## Configuration

All options go under `[tool.hatch.build.hooks.locked-deps]`:

```toml
[tool.hatch.build.hooks.locked-deps]
lock-file = "pylock.toml"
format = "pylock"
exclude = ["numpy"]
include-extras = ["test"]
```

| Option | Description |
|---|---|
| `lock-file` | Path to the lock file, relative to the project root. Only needed for non-standard file names or locations. |
| `format` | Lock file format: `pylock`, `uv`, or `requirements`. Only needed when using a non-standard file name. |
| `exclude` | List of package names to exclude from the locked dependencies. |
| `include-extras` | List of project extras whose dependencies should also be included. |
