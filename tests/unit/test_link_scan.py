from __future__ import annotations

from pathlib import Path

from endpaper.core.links import find_links

SOURCE = Path("notes/2026/07/2026-07-30-example.md")


def test_fragment_only_link() -> None:
    links = find_links("See [Q3 planning](#meeting_20260728_a1b2c3d4) for context.", source=SOURCE)
    assert len(links) == 1
    assert links[0].path is None
    assert links[0].target_id == "meeting_20260728_a1b2c3d4"
    assert links[0].text == "Q3 planning"


def test_full_relative_path_and_fragment() -> None:
    text = "[Q3](../../../meetings/2026/07/2026-07-28-q3.md#meeting_20260728_a1b2c3d4)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].path == "../../../meetings/2026/07/2026-07-28-q3.md"
    assert links[0].target_id == "meeting_20260728_a1b2c3d4"


def test_path_only_link() -> None:
    text = "[Q3](../../../meetings/2026/07/2026-07-28-q3.md)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].path == "../../../meetings/2026/07/2026-07-28-q3.md"
    assert links[0].target_id is None


def test_image_is_skipped() -> None:
    links = find_links("![alt text](pic.png)", source=SOURCE)
    assert links == ()


def test_image_before_real_link_does_not_suppress_it() -> None:
    text = "![alt](pic.png) and [Q3](#meeting_1)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].target_id == "meeting_1"


def test_link_inside_inline_code_span_is_skipped() -> None:
    text = "Use `[text](#id)` to write a link."
    links = find_links(text, source=SOURCE)
    assert links == ()


def test_double_backtick_span_containing_a_single_backtick() -> None:
    text = "See ``a `[nope](#id)` b`` here."
    links = find_links(text, source=SOURCE)
    assert links == ()


def test_fenced_triple_backtick_block_is_masked() -> None:
    text = "before\n```\n[nope](#id)\n```\nafter"
    links = find_links(text, source=SOURCE)
    assert links == ()


def test_fenced_tilde_block_is_masked() -> None:
    text = "before\n~~~\n[nope](#id)\n~~~\nafter"
    links = find_links(text, source=SOURCE)
    assert links == ()


def test_text_after_a_fence_is_scanned_normally() -> None:
    text = "```\ncode\n```\n[real](#meeting_1)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].target_id == "meeting_1"


def test_unclosed_fence_masks_to_end_of_file() -> None:
    text = "before\n```\n[nope](#id)\nstill inside\n[also nope](#id2)"
    links = find_links(text, source=SOURCE)
    assert links == ()


def test_fence_with_an_info_string() -> None:
    text = "```python\n[nope](#id)\n```\n[real](#meeting_1)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].target_id == "meeting_1"


def test_fence_with_info_string_containing_fence_char_does_not_close_early() -> None:
    text = "```` `backtick` in info\n[nope](#id)\n````\n[real](#meeting_1)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].target_id == "meeting_1"


def test_external_url_is_not_a_record_link() -> None:
    links = find_links("[site](https://example.com)", source=SOURCE)
    assert links == ()


def test_mailto_is_not_a_record_link() -> None:
    links = find_links("[email](mailto:a@example.com)", source=SOURCE)
    assert links == ()


def test_angle_bracket_destination_with_a_space() -> None:
    text = "[a](<notes/2026/07/Q3 (draft).md#note_1>)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].path == "notes/2026/07/Q3 (draft).md"
    assert links[0].target_id == "note_1"


def test_two_links_on_one_line() -> None:
    text = "[a](#meeting_1) and [b](#note_2)"
    links = find_links(text, source=SOURCE)
    assert len(links) == 2
    assert links[0].target_id == "meeting_1"
    assert links[1].target_id == "note_2"


def test_unclosed_link_is_not_matched() -> None:
    text = "[broken](#meeting_1 no closing paren here"
    links = find_links(text, source=SOURCE)
    assert links == ()


def test_no_links_in_plain_prose() -> None:
    links = find_links("Just some plain prose with no brackets at all.", source=SOURCE)
    assert links == ()


def test_reference_style_link_is_not_recognised() -> None:
    text = "[Q3 planning][ref]\n\n[ref]: ../meetings/2026/07/a.md"
    links = find_links(text, source=SOURCE)
    assert links == ()


def test_empty_destination_is_not_a_link() -> None:
    links = find_links("[text]()", source=SOURCE)
    assert links == ()


def test_fragment_only_empty_hash_is_not_a_link() -> None:
    links = find_links("[text](#)", source=SOURCE)
    assert links == ()


def test_line_numbers_are_one_indexed() -> None:
    text = "line one\nline two\n[link](#meeting_1)\nline four"
    links = find_links(text, source=SOURCE)
    assert len(links) == 1
    assert links[0].line == 3


def test_start_end_offsets_span_the_whole_link() -> None:
    text = "prefix [text](#meeting_1) suffix"
    links = find_links(text, source=SOURCE)
    link = links[0]
    assert text[link.start : link.end] == "[text](#meeting_1)"


def test_never_raises_on_pathological_input() -> None:
    pathological = [
        "",
        "[" * 50,
        "```" * 10,
        "`" * 100,
        "[a](" * 20,
        "\x00\x01[link](#id)",
    ]
    for text in pathological:
        find_links(text, source=SOURCE)  # must not raise


def test_in_tasks_field_parses_bare_comma_separated_ids() -> None:
    links = find_links(
        "meeting_20260728_a1b2c3d4,note_20260731_ff00ff00",
        source=Path("tasks.md"),
        in_tasks_field=True,
    )
    assert len(links) == 2
    assert links[0].target_id == "meeting_20260728_a1b2c3d4"
    assert links[0].path is None
    assert links[0].in_tasks_field is True
    assert links[1].target_id == "note_20260731_ff00ff00"


def test_in_tasks_field_single_id() -> None:
    links = find_links("task_a1b2", source=Path("tasks.md"), in_tasks_field=True)
    assert len(links) == 1
    assert links[0].target_id == "task_a1b2"
