from __future__ import annotations

from pathlib import Path

from choom.core.mirrors import _apply_state, find_mirrors

_SOURCE = Path("/ws/meetings/2026/07/2026-07-28-q3-planning.md")


def test_applying_a_state_changes_exactly_one_character() -> None:
    text = "- [ ] [call Terry](../../../tasks.md#task_a1b2)\n"
    mirror = find_mirrors(text, source=_SOURCE)[0]

    new_text = _apply_state(text, mirror, True)

    assert new_text != text
    diffs = [i for i in range(len(text)) if text[i] != new_text[i]]
    assert diffs == [mirror.state_offset]
    assert new_text[mirror.state_offset] == "x"


def test_link_text_indentation_prose_and_line_endings_are_byte_identical() -> None:
    text = "  - [ ] see [call Terry](../../../tasks.md#task_a1b2) before Friday\r\n"
    mirror = find_mirrors(text, source=_SOURCE)[0]

    new_text = _apply_state(text, mirror, True)

    before_state = text[: mirror.state_offset]
    after_state = text[mirror.state_offset + 1 :]
    assert new_text[: mirror.state_offset] == before_state
    assert new_text[mirror.state_offset + 1 :] == after_state


def test_mirror_already_in_target_state_produces_the_identical_text_object() -> None:
    text = "- [x] [call Terry](../../../tasks.md#task_a1b2)\n"
    mirror = find_mirrors(text, source=_SOURCE)[0]

    new_text = _apply_state(text, mirror, True)

    assert new_text is text


def test_mirror_already_open_and_asked_to_stay_open_is_identical() -> None:
    text = "- [ ] [call Terry](../../../tasks.md#task_a1b2)\n"
    mirror = find_mirrors(text, source=_SOURCE)[0]

    new_text = _apply_state(text, mirror, False)

    assert new_text is text


def test_crlf_document_round_trips() -> None:
    text = "- [ ] [call Terry](../../../tasks.md#task_a1b2)\r\n- [ ] next line\r\n"
    mirror = find_mirrors(text, source=_SOURCE)[0]

    new_text = _apply_state(text, mirror, True)

    assert new_text.count("\r\n") == text.count("\r\n")
    assert new_text.splitlines()[1] == "- [ ] next line"
    assert new_text[mirror.state_offset] == "x"


def test_lf_document_round_trips() -> None:
    text = "- [ ] [call Terry](../../../tasks.md#task_a1b2)\n- [ ] next line\n"
    mirror = find_mirrors(text, source=_SOURCE)[0]

    new_text = _apply_state(text, mirror, True)

    assert "\r" not in new_text
    assert new_text.splitlines()[1] == "- [ ] next line"


def test_uppercase_x_becomes_lowercase_x_only_when_the_state_changes() -> None:
    text = "- [X] [call Terry](../../../tasks.md#task_a1b2)\n"
    mirror = find_mirrors(text, source=_SOURCE)[0]
    assert mirror.done is True

    # Already done -- asking for done again must not touch the uppercase X.
    unchanged = _apply_state(text, mirror, True)
    assert unchanged is text

    flipped = _apply_state(text, mirror, False)
    assert flipped[mirror.state_offset] == " "
