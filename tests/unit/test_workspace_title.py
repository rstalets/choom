from __future__ import annotations

from pathlib import Path

from choom.core import workspace_title
from choom.core.models import Workspace


def test_ordinary_workspace_name() -> None:
    result = workspace_title(Workspace(root=Path("/Users/rs/work-notes")))
    assert result == "choom — work-notes"


def test_posix_root_falls_back_to_path_text() -> None:
    result = workspace_title(Workspace(root=Path("/")))
    assert result == "choom — /"


def test_windows_drive_root_falls_back_to_path_text() -> None:
    result = workspace_title(Workspace(root=Path("C:\\")))
    assert result == "choom — C:\\"


def test_non_ascii_and_spaces_pass_through_verbatim() -> None:
    result = workspace_title(Workspace(root=Path("/Users/rs/Notas de reunión")))
    assert result == "choom — Notas de reunión"


def test_result_always_begins_with_choom() -> None:
    for root in (Path("/"), Path("/tmp/x"), Path("/tmp/" + "a" * 100)):
        assert workspace_title(Workspace(root=root)).startswith("choom")


def test_workspace_title_importable_from_choom_core() -> None:
    from choom.core import workspace_title as imported

    assert imported is workspace_title


def test_control_characters_are_removed() -> None:
    result = workspace_title(Workspace(root=Path("/tmp/a\x07rm -rf")))
    assert "\x07" not in result
    assert "\x1b" not in result
    assert "\n" not in result
    assert "\r" not in result
    assert "\t" not in result


def test_bel_injection_case_matches_worked_example() -> None:
    result = workspace_title(Workspace(root=Path("/tmp/a\x07rm -rf")))
    assert result == "choom — arm -rf"


def test_name_of_only_control_characters_yields_bare_choom() -> None:
    result = workspace_title(Workspace(root=Path("/tmp/" + "\x1b\x07\x01")))
    assert result == "choom"


def test_fifty_six_character_name_is_not_truncated() -> None:
    name = "a" * 56
    result = workspace_title(Workspace(root=Path("/tmp") / name))
    assert result == f"choom — {name}"
    assert len(result) == 64


def test_fifty_seven_character_name_is_truncated_to_exactly_sixty_four() -> None:
    name = "a" * 57
    result = workspace_title(Workspace(root=Path("/tmp") / name))
    assert result == f"choom — {'a' * 55}…"
    assert len(result) == 64


def test_seventy_character_name_is_bounded() -> None:
    name = "a" * 70
    result = workspace_title(Workspace(root=Path("/tmp") / name))
    assert len(result) == 64
    assert result.endswith("…")


def test_long_non_ascii_name_is_bounded_and_uncorrupted() -> None:
    name = "Notas de reunión " * 6
    result = workspace_title(Workspace(root=Path("/tmp") / name))
    assert len(result) == 64
    assert "\ufffd" not in result


def test_never_raises_on_adversarial_or_nonexistent_root(tmp_path: Path) -> None:
    for root in (
        Path(""),
        tmp_path / "does" / "not" / "exist",
        Path("/tmp/" + "\x00" * 3),
    ):
        workspace_title(Workspace(root=root))


def test_pure_repeated_calls_return_the_same_string() -> None:
    workspace = Workspace(root=Path("/Users/rs/work-notes"))
    assert workspace_title(workspace) == workspace_title(workspace)
