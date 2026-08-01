from __future__ import annotations

from pathlib import Path

from choom.core.mirrors import find_mirrors

_SOURCE = Path("/ws/meetings/2026/07/2026-07-28-q3-planning.md")


def test_canonical_form_qualifies() -> None:
    text = "- [ ] [call Terry](../../../tasks.md#task_a1b2)\n"
    mirrors = find_mirrors(text, source=_SOURCE)
    assert len(mirrors) == 1
    assert mirrors[0].task_id == "task_a1b2"
    assert mirrors[0].done is False


def test_indented_under_a_bullet_qualifies() -> None:
    text = "  - [x] [call Terry](../../../tasks.md#task_a1b2)\n"
    mirrors = find_mirrors(text, source=_SOURCE)
    assert len(mirrors) == 1
    assert mirrors[0].done is True


def test_star_and_plus_bullets_qualify() -> None:
    for bullet in ("*", "+"):
        text = f"{bullet} [ ] [call Terry](#task_a1b2)\n"
        mirrors = find_mirrors(text, source=_SOURCE)
        assert len(mirrors) == 1, bullet


def test_fragment_only_destination_qualifies() -> None:
    text = "* [ ] [call Terry](#task_a1b2)\n"
    mirrors = find_mirrors(text, source=_SOURCE)
    assert len(mirrors) == 1
    assert mirrors[0].task_id == "task_a1b2"


def test_prose_around_the_link_is_fine() -> None:
    text = "- [ ] see [Terry](../../../tasks.md#task_a1b2) before Friday\n"
    mirrors = find_mirrors(text, source=_SOURCE)
    assert len(mirrors) == 1


def test_uppercase_state_character_reads_as_done() -> None:
    text = "- [X] [call Terry](../../../tasks.md#task_a1b2)\n"
    mirrors = find_mirrors(text, source=_SOURCE)
    assert len(mirrors) == 1
    assert mirrors[0].done is True


# --- Does not qualify ----------------------------------------------------------


def test_prose_link_with_no_checkbox_is_not_a_mirror() -> None:
    text = "As agreed, [call Terry](../../../tasks.md#task_a1b2).\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_checkbox_with_no_link_is_not_a_mirror() -> None:
    text = "- [ ] call Terry about the renewal\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_link_with_no_fragment_is_not_a_mirror() -> None:
    text = "- [ ] [call Terry](../../../tasks.md)\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_non_task_fragment_is_not_a_mirror() -> None:
    text = "- [ ] [the July meeting](../../meetings/2026/07/x.md#meeting_2026abc)\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_link_inside_a_code_span_is_excluded() -> None:
    text = "- [ ] `[call Terry](../../../tasks.md#task_a1b2)`\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_link_inside_a_fenced_code_block_is_excluded() -> None:
    text = "```\n- [ ] [call Terry](../../../tasks.md#task_a1b2)\n```\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_numbered_list_item_is_not_a_mirror() -> None:
    text = "1. [ ] [call Terry](../../../tasks.md#task_a1b2)\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_bullet_with_no_following_space_is_not_a_mirror() -> None:
    text = "-[ ] [call Terry](../../../tasks.md#task_a1b2)\n"
    assert find_mirrors(text, source=_SOURCE) == ()


def test_image_is_never_a_mirror() -> None:
    text = "- [ ] ![call Terry](../../../tasks.md#task_a1b2)\n"
    assert find_mirrors(text, source=_SOURCE) == ()


# --- Ambiguity within one line ---------------------------------------------------


def test_first_of_several_task_links_on_one_line_is_the_mirror() -> None:
    text = (
        "- [ ] [call Terry](../../../tasks.md#task_first) "
        "and [Jan](../../../tasks.md#task_second)\n"
    )
    mirrors = find_mirrors(text, source=_SOURCE)
    assert len(mirrors) == 1
    assert mirrors[0].task_id == "task_first"


def test_never_raises_on_arbitrary_text() -> None:
    for text in ("", "\n\n\n", "not a checklist at all", "- [ ] []()", "- [q] [x](y#task_1)"):
        find_mirrors(text, source=_SOURCE)  # must not raise


def test_no_mirrors_when_document_has_no_links_at_all() -> None:
    assert find_mirrors("just some prose\n\nmore prose\n", source=_SOURCE) == ()
