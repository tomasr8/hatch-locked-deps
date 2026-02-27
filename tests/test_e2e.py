from __future__ import annotations

import email.parser
import os
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path


def _build_wheel(project_dir: Path) -> Path:
    """Build a wheel from project_dir and return the path to the .whl file."""
    dist_dir = project_dir / "dist"
    dist_dir.mkdir()

    # Use the PEP 517 CLI entry point so the build hook plugin is discovered
    # via the entry point registered by *this* package (installed in the venv).
    subprocess.check_call(
        [sys.executable, "-m", "hatchling", "build", "-t", "wheel"],
        cwd=project_dir,
        env={**os.environ, "SOURCE_DATE_EPOCH": "0"},
    )

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"Expected 1 wheel, got {wheels}"
    return wheels[0]


def _wheel_requires(whl_path: Path) -> list[str]:
    """Extract Requires-Dist values from wheel METADATA."""
    with zipfile.ZipFile(whl_path) as zf:
        metadata_files = [n for n in zf.namelist() if n.endswith("/METADATA")]
        assert metadata_files, "No METADATA found in wheel"
        raw = zf.read(metadata_files[0]).decode()

    msg = email.parser.Parser().parsestr(raw)
    return msg.get_all("Requires-Dist") or []


def _write_project(
    tmp_path: Path,
    *,
    lock_file: str,
    lock_content: str,
    extra_toml: str = "",
) -> Path:
    """Scaffold a minimal hatchling project with the locked-deps hook."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "myproject").mkdir()
    (project_dir / "myproject" / "__init__.py").write_text("")
    (project_dir / lock_file).write_text(textwrap.dedent(lock_content))

    (project_dir / "pyproject.toml").write_text(
        textwrap.dedent(f"""\
        [build-system]
        requires = ["hatchling", "hatch-locked-deps"]
        build-backend = "hatchling.build"

        [project]
        name = "myproject"
        version = "0.1.0"
        requires-python = ">=3.11"

        [tool.hatch.build.hooks.locked-deps]
        {extra_toml}
    """)
    )

    return project_dir


# ---- requirements.txt ----


class TestE2ERequirements:
    def test_basic(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="requirements.txt",
            lock_content="""\
                requests==2.31.0
                urllib3==2.1.0
            """,
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "requests==2.31.0" in deps
        assert "urllib3==2.1.0" in deps

    def test_with_markers(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="requirements.txt",
            lock_content="""\
                cffi==1.16.0 ; platform_system != "Windows"
            """,
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert 'cffi==1.16.0 ; platform_system != "Windows"' in deps

    def test_exclude(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="requirements.txt",
            lock_content="""\
                requests==2.31.0
                urllib3==2.1.0
            """,
            extra_toml='exclude = ["urllib3"]',
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "requests==2.31.0" in deps
        assert not any("urllib3" in d for d in deps)


# ---- uv.lock ----


class TestE2EUvLock:
    def test_basic(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="uv.lock",
            lock_content="""\
                version = 1

                [[package]]
                name = "myproject"
                version = "0.1.0"
                source = { editable = "." }
                dependencies = [
                    { name = "requests" },
                ]

                [[package]]
                name = "requests"
                version = "2.31.0"
                source = { registry = "https://pypi.org/simple" }
            """,
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "requests==2.31.0" in deps

    def test_dev_deps_excluded(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="uv.lock",
            lock_content="""\
                version = 1

                [[package]]
                name = "myproject"
                version = "0.1.0"
                source = { editable = "." }
                dependencies = [
                    { name = "flask" },
                ]

                [package.dev-dependencies]
                dev = [
                    { name = "pytest" },
                ]

                [[package]]
                name = "flask"
                version = "3.0.0"
                source = { registry = "https://pypi.org/simple" }

                [[package]]
                name = "pytest"
                version = "8.0.0"
                source = { registry = "https://pypi.org/simple" }
            """,
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "flask==3.0.0" in deps
        assert not any("pytest" in d for d in deps)

    def test_extras(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="uv.lock",
            lock_content="""\
                version = 1

                [[package]]
                name = "myproject"
                version = "0.1.0"
                source = { editable = "." }
                dependencies = [
                    { name = "flask" },
                ]

                [package.optional-dependencies]
                postgres = [
                    { name = "psycopg2" },
                ]

                [[package]]
                name = "flask"
                version = "3.0.0"
                source = { registry = "https://pypi.org/simple" }

                [[package]]
                name = "psycopg2"
                version = "2.9.9"
                source = { registry = "https://pypi.org/simple" }
            """,
            extra_toml='include-extras = ["postgres"]',
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "flask==3.0.0" in deps
        assert 'psycopg2==2.9.9 ; extra == "postgres"' in deps


# ---- pylock.toml ----


class TestE2EPylock:
    def test_basic(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="pylock.toml",
            lock_content="""\
                lock-version = "1.0"

                [[packages]]
                name = "requests"
                version = "2.31.0"

                [[packages]]
                name = "urllib3"
                version = "2.1.0"
            """,
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "requests==2.31.0" in deps
        assert "urllib3==2.1.0" in deps

    def test_extras_excluded_by_default(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="pylock.toml",
            lock_content="""\
                lock-version = "1.0"

                [[packages]]
                name = "flask"
                version = "3.0.0"

                [[packages]]
                name = "pytest"
                version = "8.0.0"
                marker = "extra == 'dev'"
            """,
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "flask==3.0.0" in deps
        assert not any("pytest" in d for d in deps)


# ---- format inference / explicit format ----


class TestE2EFormatConfig:
    def test_explicit_format_with_custom_filename(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="locked.txt",
            lock_content="""\
                requests==2.31.0
            """,
            extra_toml="""\
                lock-file = "locked.txt"
                format = "requirements"
            """,
        )
        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "requests==2.31.0" in deps

    def test_auto_detect_prefers_pylock(self, tmp_path):
        project = _write_project(
            tmp_path,
            lock_file="pylock.toml",
            lock_content="""\
                lock-version = "1.0"

                [[packages]]
                name = "flask"
                version = "3.0.0"
            """,
        )
        # Also add a requirements.txt — pylock.toml should win
        (project / "requirements.txt").write_text("requests==2.31.0\n")

        whl = _build_wheel(project)
        deps = _wheel_requires(whl)
        assert "flask==3.0.0" in deps
        assert not any("requests" in d for d in deps)
