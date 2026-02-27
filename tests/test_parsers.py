# tests/test_parsers.py
from __future__ import annotations

import textwrap

import pytest

from hatch_locked_deps.formats import Format
from hatch_locked_deps.parsers import (
    auto_detect,
    parse_pylock_toml,
    parse_requirements_txt,
    parse_uv_lock,
)
from hatch_locked_deps.parsers.dep import Dependency


D = Dependency


# ---- requirements.txt ----


class TestParseRequirementsTxt:
    def test_simple_pinned(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("requests==2.31.0\nurllib3==2.1.0\n")
        assert parse_requirements_txt(f) == [
            D("requests", "2.31.0"),
            D("urllib3", "2.1.0"),
        ]

    def test_comments_and_blank_lines(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text(
            textwrap.dedent("""\
            # This is a comment
            requests==2.31.0

            # Another comment
            urllib3==2.1.0
        """)
        )
        assert parse_requirements_txt(f) == [
            D("requests", "2.31.0"),
            D("urllib3", "2.1.0"),
        ]

    def test_hashes_stripped(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text(
            textwrap.dedent("""\
            certifi==2024.2.2 \\
                --hash=sha256:dc383c07b76109f368f6106eee2b593b \\
                --hash=sha256:922820b53db7a7257ffbda3f597266d4
        """)
        )
        assert parse_requirements_txt(f) == [D("certifi", "2024.2.2")]

    def test_markers_preserved(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text(
            textwrap.dedent("""\
            cffi==1.16.0 ; platform_system != "Windows"
            pywin32==306 ; sys_platform == "win32"
            typing-extensions==4.9.0 ; python_version < "3.12"
        """)
        )
        assert parse_requirements_txt(f) == [
            D("cffi", "1.16.0", 'platform_system != "Windows"'),
            D("pywin32", "306", 'sys_platform == "win32"'),
            D("typing-extensions", "4.9.0", 'python_version < "3.12"'),
        ]

    def test_extras(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("urllib3[socks]==2.1.0\n")
        assert parse_requirements_txt(f) == [D("urllib3[socks]", "2.1.0")]

    def test_flags_ignored(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text(
            textwrap.dedent("""\
            --index-url https://pypi.org/simple
            -e .
            requests==2.31.0
        """)
        )
        assert parse_requirements_txt(f) == [D("requests", "2.31.0")]

    def test_empty_file(self, tmp_path):
        f = tmp_path / "requirements.txt"
        f.write_text("")
        assert parse_requirements_txt(f) == []


# ---- uv.lock ----


def _uv_lock(tmp_path, content):
    f = tmp_path / "uv.lock"
    f.write_text(textwrap.dedent(content))
    return f


class TestParseUvLockBasic:
    def test_simple(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
            source = { editable = "." }
            dependencies = [
                { name = "requests" },
                { name = "urllib3" },
            ]

            [[package]]
            name = "requests"
            version = "2.31.0"
            source = { registry = "https://pypi.org/simple" }

            [[package]]
            name = "urllib3"
            version = "2.1.0"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        assert parse_uv_lock(f, project_name="myapp") == [
            D("requests", "2.31.0"),
            D("urllib3", "2.1.0"),
        ]

    def test_resolution_markers(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
            source = { editable = "." }
            dependencies = [
                { name = "cffi" },
            ]

            [[package]]
            name = "cffi"
            version = "1.16.0"
            source = { registry = "https://pypi.org/simple" }
            resolution-marker = "platform_system != 'Windows'"
        """,
        )
        assert parse_uv_lock(f, project_name="myapp") == [
            D("cffi", "1.16.0", "platform_system != 'Windows'"),
        ]

    def test_multiple_versions_forked(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
            source = { editable = "." }
            dependencies = [
                { name = "numpy" },
            ]

            [[package]]
            name = "numpy"
            version = "1.26.4"
            source = { registry = "https://pypi.org/simple" }
            resolution-marker = "python_version < '3.12'"

            [[package]]
            name = "numpy"
            version = "2.1.0"
            source = { registry = "https://pypi.org/simple" }
            resolution-marker = "python_version >= '3.12'"
        """,
        )
        assert parse_uv_lock(f, project_name="myapp") == [
            D("numpy", "1.26.4", "python_version < '3.12'"),
            D("numpy", "2.1.0", "python_version >= '3.12'"),
        ]

    def test_no_root_raises(self, tmp_path):
        """Without a root package, raise ValueError."""
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "requests"
            version = "2.31.0"
            source = { registry = "https://pypi.org/simple" }

            [[package]]
            name = "urllib3"
            version = "2.1.0"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        with pytest.raises(ValueError, match="Root package 'myapp' not found"):
            parse_uv_lock(f, project_name="myapp")

    def test_git_deps_skipped(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
            source = { editable = "." }
            dependencies = [
                { name = "my-lib" },
                { name = "requests" },
            ]

            [[package]]
            name = "my-lib"
            version = "0.1.0"
            source = { git = "https://github.com/org/my-lib.git" }

            [[package]]
            name = "requests"
            version = "2.31.0"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        assert parse_uv_lock(f, project_name="myapp") == [D("requests", "2.31.0")]


class TestParseUvLockGraphWalk:
    def test_transitive_deps_included(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
            source = { editable = "." }
            dependencies = [
                { name = "flask" },
            ]

            [[package]]
            name = "flask"
            version = "3.0.0"
            source = { registry = "https://pypi.org/simple" }
            dependencies = [
                { name = "werkzeug" },
                { name = "jinja2" },
            ]

            [[package]]
            name = "werkzeug"
            version = "3.0.1"
            source = { registry = "https://pypi.org/simple" }

            [[package]]
            name = "jinja2"
            version = "3.1.3"
            source = { registry = "https://pypi.org/simple" }
            dependencies = [
                { name = "markupsafe" },
            ]

            [[package]]
            name = "markupsafe"
            version = "2.1.4"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        result = parse_uv_lock(f, project_name="myapp")
        assert D("flask", "3.0.0") in result
        assert D("werkzeug", "3.0.1") in result
        assert D("jinja2", "3.1.3") in result
        assert D("markupsafe", "2.1.4") in result

    def test_dev_deps_excluded(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
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
        result = parse_uv_lock(f, project_name="myapp")
        assert D("flask", "3.0.0") in result
        assert D("pytest", "8.0.0") not in result

    def test_shared_transitive_dep_included(self, tmp_path):
        """A package reachable from both main and dev should be included."""
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
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
            dependencies = [
                { name = "packaging" },
            ]

            [[package]]
            name = "pytest"
            version = "8.0.0"
            source = { registry = "https://pypi.org/simple" }
            dependencies = [
                { name = "packaging" },
            ]

            [[package]]
            name = "packaging"
            version = "24.0"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        result = parse_uv_lock(f, project_name="myapp")
        assert D("flask", "3.0.0") in result
        assert D("packaging", "24.0") in result
        assert D("pytest", "8.0.0") not in result


class TestParseUvLockExtras:
    def test_include_extras(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
            source = { editable = "." }
            dependencies = [
                { name = "flask" },
            ]

            [package.optional-dependencies]
            postgres = [
                { name = "psycopg2" },
            ]
            redis = [
                { name = "redis" },
            ]

            [[package]]
            name = "flask"
            version = "3.0.0"
            source = { registry = "https://pypi.org/simple" }

            [[package]]
            name = "psycopg2"
            version = "2.9.9"
            source = { registry = "https://pypi.org/simple" }

            [[package]]
            name = "redis"
            version = "5.0.1"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        result = parse_uv_lock(f, project_name="myapp", include_extras=["postgres"])
        assert D("flask", "3.0.0") in result
        assert D("psycopg2", "2.9.9", 'extra == "postgres"') in result
        assert not any(d.name == "redis" for d in result)

    def test_extra_with_resolution_marker(self, tmp_path):
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
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
            resolution-marker = "sys_platform != 'win32'"
        """,
        )
        result = parse_uv_lock(f, project_name="myapp", include_extras=["postgres"])
        assert D("psycopg2", "2.9.9", "extra == \"postgres\" and sys_platform != 'win32'") in result

    def test_extra_transitive_deps_get_marker(self, tmp_path):
        """Transitive deps of extras should also get the extra marker."""
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
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
            dependencies = [
                { name = "libpq" },
            ]

            [[package]]
            name = "libpq"
            version = "1.0.0"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        result = parse_uv_lock(f, project_name="myapp", include_extras=["postgres"])
        assert D("flask", "3.0.0") in result
        assert D("psycopg2", "2.9.9", 'extra == "postgres"') in result
        assert D("libpq", "1.0.0", 'extra == "postgres"') in result

    def test_extra_shared_dep_not_duplicated(self, tmp_path):
        """If main and extra share a transitive dep, it goes under main (no marker)."""
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "myapp"
            version = "1.0.0"
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
            dependencies = [
                { name = "click" },
            ]

            [[package]]
            name = "psycopg2"
            version = "2.9.9"
            source = { registry = "https://pypi.org/simple" }
            dependencies = [
                { name = "click" },
            ]

            [[package]]
            name = "click"
            version = "8.1.7"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        result = parse_uv_lock(f, project_name="myapp", include_extras=["postgres"])
        # click is reachable via main (flask), so no extra marker
        assert D("click", "8.1.7") in result
        assert not any(d.name == "click" and d.markers for d in result)

    def test_project_name_selects_root(self, tmp_path):
        """In a workspace, project_name identifies the correct root."""
        f = _uv_lock(
            tmp_path,
            """\
            version = 1

            [[package]]
            name = "lib-a"
            version = "0.1.0"
            source = { editable = "packages/lib-a" }
            dependencies = [
                { name = "six" },
            ]

            [[package]]
            name = "myapp"
            version = "1.0.0"
            source = { editable = "." }
            dependencies = [
                { name = "flask" },
            ]

            [[package]]
            name = "flask"
            version = "3.0.0"
            source = { registry = "https://pypi.org/simple" }

            [[package]]
            name = "six"
            version = "1.16.0"
            source = { registry = "https://pypi.org/simple" }
        """,
        )
        result = parse_uv_lock(f, project_name="myapp")
        assert D("flask", "3.0.0") in result
        assert D("six", "1.16.0") not in result


# ---- pylock.toml ----


class TestParsePylockToml:
    def test_simple(self, tmp_path):
        f = tmp_path / "pylock.toml"
        f.write_text(
            textwrap.dedent("""\
            lock-version = "1.0"

            [[packages]]
            name = "requests"
            version = "2.31.0"

            [[packages]]
            name = "urllib3"
            version = "2.1.0"
        """)
        )
        assert parse_pylock_toml(f) == [
            D("requests", "2.31.0"),
            D("urllib3", "2.1.0"),
        ]

    def test_markers(self, tmp_path):
        f = tmp_path / "pylock.toml"
        f.write_text(
            textwrap.dedent("""\
            lock-version = "1.0"

            [[packages]]
            name = "cffi"
            version = "1.16.0"
            marker = "platform_system != 'Windows'"

            [[packages]]
            name = "pywin32"
            version = "306"
            marker = "sys_platform == 'win32'"
        """)
        )
        assert parse_pylock_toml(f) == [
            D("cffi", "1.16.0", "platform_system != 'Windows'"),
            D("pywin32", "306", "sys_platform == 'win32'"),
        ]

    def test_extras_excluded_by_default(self, tmp_path):
        f = tmp_path / "pylock.toml"
        f.write_text(
            textwrap.dedent("""\
            lock-version = "1.0"

            [[packages]]
            name = "flask"
            version = "3.0.0"

            [[packages]]
            name = "pytest"
            version = "8.0.0"
            marker = "extra == 'dev'"

            [[packages]]
            name = "sphinx"
            version = "7.2.6"
            marker = "extra == 'docs'"
        """)
        )
        result = parse_pylock_toml(f)
        assert D("flask", "3.0.0") in result
        assert not any(d.name == "pytest" for d in result)
        assert not any(d.name == "sphinx" for d in result)

    def test_include_extras(self, tmp_path):
        f = tmp_path / "pylock.toml"
        f.write_text(
            textwrap.dedent("""\
            lock-version = "1.0"

            [[packages]]
            name = "flask"
            version = "3.0.0"

            [[packages]]
            name = "psycopg2"
            version = "2.9.9"
            marker = "extra == 'postgres'"

            [[packages]]
            name = "redis"
            version = "5.0.1"
            marker = "extra == 'redis'"
        """)
        )
        result = parse_pylock_toml(f, include_extras=["postgres"])
        assert D("flask", "3.0.0") in result
        assert D("psycopg2", "2.9.9", "extra == 'postgres'") in result
        assert not any(d.name == "redis" for d in result)

    def test_empty_packages(self, tmp_path):
        f = tmp_path / "pylock.toml"
        f.write_text('lock-version = "1.0"\n')
        assert parse_pylock_toml(f) == []


# ---- auto_detect ----


class TestAutoDetect:
    def test_falls_back_to_uv_lock(self, tmp_path):
        (tmp_path / "uv.lock").write_text("version = 1\n")
        (tmp_path / "requirements.txt").write_text("")
        fmt, _path = auto_detect(tmp_path)
        assert fmt == Format.UV

    def test_no_lock_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No lock file found"):
            auto_detect(tmp_path)
