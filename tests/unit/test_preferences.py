from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from choom.core import preferences
from choom.core.errors import UsageError
from choom.core.models import Workspace

#: Captured at module-collection time, before any fixture runs -- the autouse
#: `_isolated_profile_and_preferences_roots` fixture (tests/conftest.py)
#: monkeypatches `preferences.preferences_root` for the whole test suite, and
#: the tests below that exercise the *real* implementation on this run's host
#: platform need to bypass that patch rather than fight it. Rebinding the
#: module attribute later does not affect this already-captured function
#: object.
_real_preferences_root = preferences.preferences_root

# --- T002: preferences_root() -- the single overridable resolver -----------
#
# `_windows_candidate`/`_posix_candidate` are pure (no env-var read, no
# `os.name`/`Path.home()` dispatch) precisely so the Windows branch is
# unit-testable from any host -- `pathlib.WindowsPath` cannot be
# instantiated on a non-Windows host, and Python's own dispatch for that
# reads the *real* `os.name` even if a test patches the attribute, so
# `preferences_root()` itself can only be exercised end-to-end on the host
# it is actually running on (see the module's docstring). The public
# function is still covered below, on this run's real platform.
#
# Windows-flavoured inputs are literal drive-letter strings, deliberately
# not built from `tmp_path`: a POSIX `tmp_path` (e.g. "/private/var/...")
# has no drive letter, so `PureWindowsPath.is_absolute()` on it is correctly
# False -- Windows absolute paths require a drive (or a UNC root) -- which
# would make every "set" case silently fall through to the same branch as
# "unset" and defeat the point of the test.


def test_windows_candidate_uses_localappdata_when_set() -> None:
    result = preferences._windows_candidate(
        "C:\\Users\\pat\\AppData\\Local", "C:\\Users\\pat\\AppData\\Roaming", "C:\\Users\\pat"
    )
    assert result == "C:\\Users\\pat\\AppData\\Local\\choom"


def test_windows_candidate_falls_back_to_appdata_when_localappdata_unset() -> None:
    result = preferences._windows_candidate(
        "", "C:\\Users\\pat\\AppData\\Roaming", "C:\\Users\\pat"
    )
    assert result == "C:\\Users\\pat\\AppData\\Roaming\\choom"


def test_windows_candidate_falls_back_to_home_when_neither_set() -> None:
    result = preferences._windows_candidate("", "", "C:\\Users\\pat")
    assert result == "C:\\Users\\pat\\AppData\\Local\\choom"


def test_windows_candidate_empty_localappdata_falls_through_to_appdata() -> None:
    # research-cited bug: a set-but-empty env var must not win over the next
    # candidate.
    result = preferences._windows_candidate(
        "", "C:\\Users\\pat\\AppData\\Roaming", "C:\\Users\\pat"
    )
    assert result == "C:\\Users\\pat\\AppData\\Roaming\\choom"


def test_windows_candidate_relative_localappdata_falls_through_to_appdata() -> None:
    # The one bug this function must not have: a relative base would
    # resolve against the process's cwd, which for choom is usually inside a
    # workspace.
    result = preferences._windows_candidate(
        "relative\\path", "C:\\Users\\pat\\AppData\\Roaming", "C:\\Users\\pat"
    )
    assert result == "C:\\Users\\pat\\AppData\\Roaming\\choom"


def test_windows_candidate_relative_appdata_falls_through_to_home() -> None:
    result = preferences._windows_candidate("", "relative\\path", "C:\\Users\\pat")
    assert result == "C:\\Users\\pat\\AppData\\Local\\choom"


def test_posix_candidate_uses_xdg_config_home_when_set(tmp_path: Path) -> None:
    result = preferences._posix_candidate(str(tmp_path / "xdg"), str(tmp_path / "home"))
    assert result == str(tmp_path / "xdg" / "choom")


def test_posix_candidate_falls_back_to_home_config_when_unset(tmp_path: Path) -> None:
    result = preferences._posix_candidate("", str(tmp_path / "home"))
    assert result == str(tmp_path / "home" / ".config" / "choom")


def test_posix_candidate_empty_xdg_config_home_falls_back(tmp_path: Path) -> None:
    result = preferences._posix_candidate("", str(tmp_path / "home"))
    assert result == str(tmp_path / "home" / ".config" / "choom")


def test_posix_candidate_relative_xdg_config_home_falls_back(tmp_path: Path) -> None:
    result = preferences._posix_candidate("relative/path", str(tmp_path / "home"))
    assert result == str(tmp_path / "home" / ".config" / "choom")


# --- preferences_root() itself, on this run's real platform -----------------
#
# These call `_real_preferences_root()` (captured above), not
# `preferences.preferences_root()`, precisely because the autouse fixture
# patches the latter for the whole suite (T003) -- these tests exist to
# cover the *unpatched* implementation's env-var precedence for real, on
# whichever platform this run's host is. `os.path.expanduser("~")` reads
# `HOME`/`USERPROFILE`, which the same autouse fixture also redirects to a
# scratch directory, so the fallback branch below is exercised safely too.
# Skipped on a real Windows runner, where the dispatch takes the other
# branch (this project's CI is Linux-only; the Windows branch's logic is
# covered above instead, via the pure candidate functions).


@pytest.mark.skipif(os.name == "nt", reason="posix-only assertion; Windows is covered above")
def test_preferences_root_uses_xdg_config_home_on_posix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert _real_preferences_root() == tmp_path / "xdg" / "choom"


@pytest.mark.skipif(os.name == "nt", reason="posix-only assertion; Windows is covered above")
def test_preferences_root_falls_back_to_home_config_on_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert _real_preferences_root() == Path.home() / ".config" / "choom"


def test_preferences_root_never_creates_the_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = _real_preferences_root()
    assert not root.exists()


# --- T004: get_view_orientation() -- every failure mode returns "horizontal" -
#
# `preferences.preferences_root()` below is the *patched* version (T003's
# autouse fixture), which is exactly what these tests want: every read/write
# lands inside this test's isolated scratch directory, never a developer's
# real profile.

_PREFS_FILENAME = "preferences.toml"


def _prefs_path() -> Path:
    return preferences.preferences_root() / _PREFS_FILENAME


def test_get_view_orientation_file_absent() -> None:
    assert not _prefs_path().exists()
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = "vertical"\n', encoding="utf-8")

    real_open = Path.open

    def _raise_oserror(self: Path, *args: object, **kwargs: object) -> object:
        if self == path:
            raise OSError("permission denied")
        return real_open(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", _raise_oserror)
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_invalid_toml() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid toml [[[", encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_no_view_table() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[other]\nkey = "value"\n', encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_view_not_a_table() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("view = 1\n", encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_no_orientation_key() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[view]\nother = 1\n", encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_orientation_not_a_string() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[view]\norientation = 1\n", encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_orientation_a_bool() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[view]\norientation = true\n", encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_orientation_a_list() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = ["vertical"]\n', encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_orientation_illegal_string() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = "sideways"\n', encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_matching_is_case_sensitive() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = "Vertical"\n', encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_horizontal_happy_path() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = "horizontal"\n', encoding="utf-8")
    assert preferences.get_view_orientation() == "horizontal"


def test_get_view_orientation_vertical_happy_path() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = "vertical"\n', encoding="utf-8")
    assert preferences.get_view_orientation() == "vertical"


# --- T005: set_view_orientation() -------------------------------------------


def test_set_view_orientation_creates_file_from_absent() -> None:
    path = _prefs_path()
    assert not path.exists()
    preferences.set_view_orientation("vertical")
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["view"]["orientation"] == "vertical"


def test_set_view_orientation_replaces_in_place() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = "vertical"\n', encoding="utf-8")
    preferences.set_view_orientation("horizontal")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["view"]["orientation"] == "horizontal"


def test_set_view_orientation_preserves_comments_key_order_and_unknown_keys() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# a hand-written comment\n"
        "[view]\n"
        'nickname = "my-view"\n'
        'orientation = "vertical"\n'
        "another = 1\n"
        "\n"
        "[unrelated]\n"
        'key = "value"\n',
        encoding="utf-8",
    )
    preferences.set_view_orientation("horizontal")
    text = path.read_text(encoding="utf-8")
    assert "# a hand-written comment" in text
    assert 'nickname = "my-view"' in text
    assert "another = 1" in text
    data = tomllib.loads(text)
    assert data["view"]["orientation"] == "horizontal"
    assert data["view"]["nickname"] == "my-view"
    assert data["view"]["another"] == 1
    assert data["unrelated"]["key"] == "value"
    # nickname (which precedes orientation in the original) still precedes it.
    assert text.index("nickname") < text.index("orientation")


def test_set_view_orientation_inserts_key_as_first_line_when_table_exists_without_it() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[view]\n# a comment\n", encoding="utf-8")
    preferences.set_view_orientation("vertical")
    text = path.read_text(encoding="utf-8")
    assert "# a comment" in text
    data = tomllib.loads(text)
    assert data["view"]["orientation"] == "vertical"


def test_set_view_orientation_crlf_preserved() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    original = '[view]\r\norientation = "horizontal"\r\n'
    path.write_bytes(original.encode("utf-8"))

    preferences.set_view_orientation("vertical")

    raw = path.read_bytes()
    assert b"\r\n" in raw
    assert raw.replace(b"\r\n", b"").find(b"\n") == -1  # no bare LF snuck in
    data = tomllib.loads(raw.decode("utf-8"))
    assert data["view"]["orientation"] == "vertical"


def test_set_view_orientation_illegal_value_writes_nothing() -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[view]\norientation = "horizontal"\n', encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(UsageError):
        preferences.set_view_orientation("sideways")

    assert path.read_bytes() == before


def test_set_view_orientation_illegal_value_when_file_absent_writes_nothing() -> None:
    path = _prefs_path()
    assert not path.exists()

    with pytest.raises(UsageError):
        preferences.set_view_orientation("sideways")

    assert not path.exists()


def test_set_view_orientation_illegal_value_message_names_value_and_accepted() -> None:
    with pytest.raises(
        UsageError, match="view must be one of horizontal, vertical; got 'sideways'"
    ):
        preferences.set_view_orientation("sideways")


def test_set_view_orientation_idempotent() -> None:
    preferences.set_view_orientation("vertical")
    first = _prefs_path().read_bytes()
    preferences.set_view_orientation("vertical")
    second = _prefs_path().read_bytes()
    assert first == second


def test_set_view_orientation_round_trips_through_get() -> None:
    assert preferences.get_view_orientation() == "horizontal"
    preferences.set_view_orientation("vertical")
    assert preferences.get_view_orientation() == "vertical"
    preferences.set_view_orientation("horizontal")
    assert preferences.get_view_orientation() == "horizontal"


def test_set_view_orientation_never_touches_a_workspace(tmp_workspace: Workspace) -> None:
    # FR-024: no `Workspace` parameter, and no way to find one -- confirmed by
    # snapshotting the workspace root before and after a write.
    before = {p: p.read_bytes() for p in tmp_workspace.root.rglob("*") if p.is_file()}
    preferences.set_view_orientation("vertical")
    after = {p: p.read_bytes() for p in tmp_workspace.root.rglob("*") if p.is_file()}
    assert before == after
