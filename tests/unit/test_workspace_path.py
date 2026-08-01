from __future__ import annotations

from choom.tui.collection_bar import shorten_workspace_path


def test_home_prefix_becomes_tilde(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/notes/work"

    result = shorten_workspace_path(path, 80)

    assert result == "~/notes/work"


def test_path_not_under_home_is_unchanged_when_it_fits(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/srv/shared/notes"

    result = shorten_workspace_path(path, 80)

    assert result == "/srv/shared/notes"


def test_path_that_fits_is_returned_verbatim(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "~/wk"
    result = shorten_workspace_path("/Users/ryan/wk", 80)
    assert result == path


def test_long_path_elides_from_the_left_with_ellipsis_slash(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/OneDrive/Documents/notes/work/2026"

    result = shorten_workspace_path(path, 20)

    assert result.startswith("…/")
    assert len(result) <= 20


def test_final_component_is_always_kept_whole(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/OneDrive/Documents/notes/work/2026"

    result = shorten_workspace_path(path, 20)

    assert result.endswith("2026")


def test_final_component_survives_even_when_narrower_than_the_component_itself(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/a-very-long-final-directory-name-indeed"

    result = shorten_workspace_path(path, 5)

    # The path never disappears entirely, even when it cannot fit -- the
    # final component (the part that identifies the workspace) stays intact
    # rather than being truncated mid-word (FR-036, spec edge case).
    assert result.endswith("a-very-long-final-directory-name-indeed")


def test_shortening_keeps_whole_components_not_partial_ones(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/OneDrive/Documents/notes/work/2026"

    result = shorten_workspace_path(path, 25)

    # No component in the result is a fragment of a longer directory name.
    tail = result[2:] if result.startswith("…/") else result
    for component in tail.split("/"):
        assert component in path.split("/")


def test_spaces_and_non_ascii_render_as_is(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/OneDrive - Cömpany/nötes"

    result = shorten_workspace_path(path, 80)

    assert result == "~/OneDrive - Cömpany/nötes"


def test_spaces_and_non_ascii_survive_even_when_elided(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/OneDrive - Cömpany/team notes/nötes"

    result = shorten_workspace_path(path, 15)

    assert "nötes" in result
    assert "\ufffd" not in result  # no mangled encoding


def test_no_filesystem_access(monkeypatch, tmp_path) -> None:
    # A path that does not exist on disk still shortens correctly -- this is
    # pure string arithmetic, never a filesystem check (research R9).
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    path = str(tmp_path / "home" / "does" / "not" / "exist" / "at" / "all")

    result = shorten_workspace_path(path, 15)

    assert result  # renders without raising or touching disk
    assert result.endswith("all")


def test_available_width_at_or_above_full_length_returns_unshortened(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/Users/ryan")
    path = "/Users/ryan/notes"
    homed = "~/notes"

    assert shorten_workspace_path(path, len(homed)) == homed


def test_backslash_separated_path_does_not_crash(monkeypatch) -> None:
    # Real Windows-path behaviour is exercised on Windows itself (Polish
    # phase T039); this only guards against a crash when the separator
    # this function sees is not "/" on the platform running the test.
    monkeypatch.setenv("HOME", "C:\\Users\\ryan")
    path = "C:\\Users\\ryan\\OneDrive\\notes\\work\\2026"

    result = shorten_workspace_path(path, 20)

    assert result  # renders without raising
    assert "2026" in result
