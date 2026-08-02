"""Unit tests for bare-URL-to-markdown-link conversion on save
(018-automatic-link-detection). The three corpora here mirror
specs/018-automatic-link-detection/contracts/text-format.md verbatim -- Corpus A
(converted, 25 rows), Corpus B (must-not-change, 18 rows), and Corpus C
(adversarial, 15 rows) -- plus the idempotency and newline-count invariants the
plan leans on hardest.
"""

from __future__ import annotations

import pytest

from choom.core.links import (
    _mask_angle,
    _mask_comments,
    _mask_for_bare_urls,
    _mask_frontmatter,
    _mask_links,
    _mask_refdefs,
    _trim_bare_url,
    format_bare_urls,
)
from choom.core.models import UrlConversion

# --- T005: _mask_frontmatter --------------------------------------------------


def test_mask_frontmatter_blanks_the_block() -> None:
    text = "---\ntitle: https://example.com/a\n---\nbody https://example.com/b\n"
    masked = _mask_frontmatter(text)
    assert len(masked) == len(text)
    assert "https://example.com/a" not in masked
    assert "https://example.com/b" in masked
    assert masked.count("\n") == text.count("\n")


def test_mask_frontmatter_leaves_a_document_with_no_frontmatter_untouched() -> None:
    text = "no frontmatter here, just https://example.com/a\n"
    assert _mask_frontmatter(text) == text


def test_mask_frontmatter_leaves_an_unterminated_block_untouched() -> None:
    text = "---\ntitle: unterminated https://example.com/a\nbody text\n"
    assert _mask_frontmatter(text) == text


def test_mask_frontmatter_prevents_a_document_from_disappearing() -> None:
    """The evidence this mask exists at all (research R3): an unquoted YAML
    scalar starting with `[` becomes a flow sequence, and without this mask,
    format_bare_urls would turn a parseable frontmatter block into one that
    is not."""
    from pathlib import Path

    from choom.core.documents import _parse_document

    text = (
        "---\n"
        "id: note_20260730_a1b2c3d4\n"
        "title: https://example.com/a\n"
        "type: note\n"
        "tags: []\n"
        "created: 2026-07-30\n"
        "updated: 2026-07-30\n"
        "---\n"
        "body\n"
    )
    new_text, conversions = format_bare_urls(text)
    assert conversions == ()
    assert new_text == text
    doc, warning = _parse_document(new_text, Path("x.md"))
    assert doc is not None
    assert warning is None


# --- T006: _mask_comments -----------------------------------------------------


def test_mask_comments_blanks_a_single_line_comment() -> None:
    text = "- [ ] call Terry <!-- id:task_a1b2 links:meeting_1 created:2026-07-30 -->\n"
    masked = _mask_comments(text)
    assert len(masked) == len(text)
    assert "id:task_a1b2" not in masked
    assert "- [ ] call Terry" in masked


def test_mask_comments_blanks_a_multiline_comment() -> None:
    text = "before\n<!--\nsee https://example.com/a\n-->\nafter\n"
    masked = _mask_comments(text)
    assert len(masked) == len(text)
    assert masked.count("\n") == text.count("\n")
    assert "https://example.com/a" not in masked
    assert "before" in masked and "after" in masked


def test_mask_comments_masks_an_unterminated_comment_to_end_of_file() -> None:
    text = "before <!-- never closes https://example.com/a\nmore text\n"
    masked = _mask_comments(text)
    assert len(masked) == len(text)
    assert "https://example.com/a" not in masked
    assert "before" in masked


# --- T007: _mask_links ---------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "[a](https://x.com/plain)",
        "![alt](https://x.com/a.png)",
        "[a](https://x.com/Foo_(bar))",
        "[a](<https://x.com/Foo_(bar)>)",
        "[a](<notes/Q3 (draft).md#note_1>)",
        "[https://a.example](https://a.example)",
    ],
)
def test_mask_links_blanks_the_whole_span(text: str) -> None:
    masked = _mask_links(text)
    assert len(masked) == len(text)
    assert masked.strip() == ""


def test_mask_links_leaves_surrounding_text_alone() -> None:
    text = "before [a](https://x.com/1) after https://x.com/2 end"
    masked = _mask_links(text)
    assert len(masked) == len(text)
    assert "before" in masked
    assert "after" in masked
    assert "https://x.com/2" in masked  # not part of any link -- untouched
    assert "https://x.com/1" not in masked


def test_mask_links_does_not_swallow_the_rest_of_the_file_on_an_unclosed_bracket() -> None:
    text = "[unclosed\n\nplain https://example.com/a\n"
    masked = _mask_links(text)
    assert len(masked) == len(text)
    assert "https://example.com/a" in masked


def test_mask_links_leaves_a_double_bracket_wiki_tag_alone() -> None:
    text = "[[wiki]] https://example.com/a"
    masked = _mask_links(text)
    assert len(masked) == len(text)
    assert "[[wiki]]" in masked
    assert "https://example.com/a" in masked


# --- T008: _mask_angle ---------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "<https://example.com>",
        '<a href="https://example.com">x</a>',
    ],
)
def test_mask_angle_blanks_autolinks_and_html_tags(text: str) -> None:
    masked = _mask_angle(text)
    assert len(masked) == len(text)
    assert "https://example.com" not in masked


def test_mask_angle_backstops_an_unbalanced_paren_inside_a_link_destination() -> None:
    """The case _mask_links's paren-depth counter cannot resolve (research
    R2): an angle-wrapped destination whose interior parens are unbalanced.
    _mask_angle catches the `<...>` on its own terms, with no paren
    counting at all."""
    text = "[a](<https://x.com/Q3 (draft>)"
    combined = _mask_angle(_mask_links(text))
    assert len(combined) == len(text)
    assert "https://x.com/Q3" not in combined


# --- T009: _mask_refdefs --------------------------------------------------------


def test_mask_refdefs_blanks_a_reference_definition() -> None:
    text = "[spec]: https://example.com/spec\n"
    masked = _mask_refdefs(text)
    assert len(masked) == len(text)
    assert "https://example.com/spec" not in masked


def test_mask_refdefs_leaves_ordinary_text_alone() -> None:
    text = "just prose with https://example.com/a in it\n"
    assert _mask_refdefs(text) == text


# --- T010: the composed mask pipeline -------------------------------------------


_ALL_CORPUS_TEXTS = [
    "See https://example.com/spec for details.",
    "---\ntitle: https://example.com/a\n---\nbody https://example.com/b\n",
    "```\ncurl https://api.example.com/v1\n```\n",
    "[a](https://x.com/Foo_(bar)) and https://example.com/free\n",
    '<https://example.com> and <a href="https://example.com">x</a>\n',
    "[spec]: https://example.com/spec\nSee [spec] for more.\n",
    "- [ ] call Terry <!-- id:task_a1b2 links:meeting_1 created:2026-07-30 -->\n",
]


@pytest.mark.parametrize("text", _ALL_CORPUS_TEXTS)
def test_mask_pipeline_is_length_preserving(text: str) -> None:
    masked = _mask_for_bare_urls(text)
    assert len(masked) == len(text)
    assert masked.count("\n") == text.count("\n")
    assert masked.count("\r") == text.count("\r")


# --- T011: the candidate scanner (via format_bare_urls) -------------------------


def test_candidate_fails_the_leading_boundary_when_not_starting_a_token() -> None:
    text = "xhttps://example.com/a"
    new_text, conversions = format_bare_urls(text)
    assert conversions == ()
    assert new_text == text


def test_candidate_rejects_a_bracketed_host() -> None:
    text = "https://[::1]/status"
    new_text, conversions = format_bare_urls(text)
    assert conversions == ()
    assert new_text == text


def test_candidate_rejects_a_bare_scheme_with_no_host() -> None:
    text = "text https:// more"
    new_text, conversions = format_bare_urls(text)
    assert conversions == ()
    assert new_text == text


# --- T012: the emitter -----------------------------------------------------------


def test_emit_only_ever_wraps() -> None:
    text = "See https://example.com/a for details."
    new_text, conversions = format_bare_urls(text)
    assert len(conversions) == 1
    conv = conversions[0]
    assert isinstance(conv, UrlConversion)
    assert text[conv.start : conv.end] == conv.url
    assert conv.url in conv.replacement
    assert conv.replacement.count(conv.url) == 2
    assert len(conv.replacement) > len(conv.url)


def test_emit_inverse_reproduces_the_original_over_corpus_a() -> None:
    """Deleting the four added characters and the duplicated URL reproduces
    the input exactly -- the mechanical form of FR-001's core promise.
    Conversions are non-overlapping and ascending by `start` (invariant #6),
    so each replacement's occurrence in `new_text` can be found in order
    starting right after the previous one ended."""
    for text in _CORPUS_A_TEXTS():
        new_text, conversions = format_bare_urls(text)
        pieces: list[str] = []
        pos = 0
        for conv in conversions:
            found = new_text.index(conv.replacement, pos)
            pieces.append(new_text[pos:found])
            pieces.append(conv.url)
            pos = found + len(conv.replacement)
        pieces.append(new_text[pos:])
        restored = "".join(pieces)
        assert restored == text, f"inverse failed for {text!r}"


# --- T020: the trailing-boundary trim -------------------------------------------


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("https://example.com/a.", "https://example.com/a"),
        ("https://example.com/a,", "https://example.com/a"),
        ("https://example.com/a:", "https://example.com/a"),
        ("https://example.com/a;", "https://example.com/a"),
        ("https://example.com/a!", "https://example.com/a"),
        ("https://example.com/a?", "https://example.com/a"),  # trailing ? is dropped (FR-013)
        ("https://example.com/a?q=1", "https://example.com/a?q=1"),  # ? mid-run is kept
        ("https://example.com/a)", "https://example.com/a"),  # unbalanced -- dropped
        ("https://example.com/a(bar)", "https://example.com/a(bar)"),  # balanced -- kept
        ("https://example.com/", "https://example.com/"),  # trailing slash kept
        ("https://example.com/a...", "https://example.com/a"),
        ("https://example.com/a).", "https://example.com/a"),
    ],
)
def test_trim_bare_url(candidate: str, expected: str) -> None:
    assert _trim_bare_url(candidate) == expected


# --- T021: Corpus A -- converted (25 rows) --------------------------------------


def _CORPUS_A_TEXTS() -> list[str]:
    return [row[0] for row in _CORPUS_A]


_CORPUS_A: list[tuple[str, str]] = [
    (
        "See https://example.com/spec for details.",
        "See [https://example.com/spec](https://example.com/spec) for details.",
    ),
    (
        "Read https://example.com/a.",
        "Read [https://example.com/a](https://example.com/a).",
    ),
    (
        "Read https://example.com/a, then stop",
        "Read [https://example.com/a](https://example.com/a), then stop",
    ),
    (
        "(https://example.com/a)",
        "([https://example.com/a](https://example.com/a))",
    ),
    (
        "https://en.wikipedia.org/wiki/Foo_(bar)",
        "[https://en.wikipedia.org/wiki/Foo_(bar)](<https://en.wikipedia.org/wiki/Foo_(bar)>)",
    ),
    (
        "(https://en.wikipedia.org/wiki/Foo_(bar))",
        "([https://en.wikipedia.org/wiki/Foo_(bar)](<https://en.wikipedia.org/wiki/Foo_(bar)>))",
    ),
    (
        '"https://example.com/a"',
        '"[https://example.com/a](https://example.com/a)"',
    ),
    (
        "https://example.com/a?q=1&r=2#frag",
        "[https://example.com/a?q=1&r=2#frag](https://example.com/a?q=1&r=2#frag)",
    ),
    (
        "http://legacy.internal/report",
        "[http://legacy.internal/report](http://legacy.internal/report)",
    ),
    (
        "**https://example.com/a**",
        "**[https://example.com/a](https://example.com/a)**",
    ),
    (
        "*https://example.com/a*",
        "*[https://example.com/a](https://example.com/a)*",
    ),
    (
        "- item https://example.com/a, next",
        "- item [https://example.com/a](https://example.com/a), next",
    ),
    (
        "a https://x.com/1 b https://x.com/2 c",
        "a [https://x.com/1](https://x.com/1) b [https://x.com/2](https://x.com/2) c",
    ),
    (
        "# Heading https://example.com/a",
        "# Heading [https://example.com/a](https://example.com/a)",
    ),
    (
        "HTTPS://EXAMPLE.COM/A",
        "[HTTPS://EXAMPLE.COM/A](HTTPS://EXAMPLE.COM/A)",
    ),
    (
        "see https://example.com/a; also",
        "see [https://example.com/a](https://example.com/a); also",
    ),
    (
        "done https://example.com/a!",
        "done [https://example.com/a](https://example.com/a)!",
    ),
    (
        "| https://example.com/a | next |",
        "| [https://example.com/a](https://example.com/a) | next |",
    ),
    (
        "> quoted https://example.com/a here",
        "> quoted [https://example.com/a](https://example.com/a) here",
    ),
    (
        "trailing slash https://example.com/",
        "trailing slash [https://example.com/](https://example.com/)",
    ),
    (
        "stray paren https://example.com/a)",
        "stray paren [https://example.com/a](https://example.com/a))",
    ),
    (
        "both https://example.com/a).",
        "both [https://example.com/a](https://example.com/a)).",
    ),
    (
        "ellipsis https://example.com/a...",
        "ellipsis [https://example.com/a](https://example.com/a)...",
    ),
    (
        "(see https://example.com/a).",
        "(see [https://example.com/a](https://example.com/a)).",
    ),
    (
        "    https://example.com/a",
        "    [https://example.com/a](https://example.com/a)",
    ),
]

assert len(_CORPUS_A) == 25


@pytest.mark.parametrize(("text", "expected"), _CORPUS_A)
def test_corpus_a_produces_the_exact_expected_output(text: str, expected: str) -> None:
    new_text, _conversions = format_bare_urls(text)
    assert new_text == expected


# --- T022: Corpus B -- byte-identical, no conversion (18 rows) ------------------


_CORPUS_B: list[str] = [
    "```\ncurl https://api.example.com/v1\n```",
    "~~~\nhttps://example.com/a\n~~~",
    "```\nunclosed fence https://example.com/a",
    "`https://example.com`",
    "[the spec](https://example.com/spec)",
    "[https://a.example](https://a.example)",
    "[a](https://x.com/Foo_(bar))",
    "[a](<https://x.com/Foo_(bar)>)",
    "<https://example.com>",
    "![screenshot](https://example.com/a.png)",
    "[spec]: https://example.com/spec",
    '<a href="https://example.com">x</a>',
    "- [ ] call Terry <!-- id:task_a1b2 links:meeting_1 created:2026-07-30 -->",
    "<!--\nsee https://example.com/a\n-->",
    "---\ntitle: https://example.com/a\n---\n",
    "text https:// more",
    "xhttps://example.com/a",
    "https://[::1]/status",
]

assert len(_CORPUS_B) == 18


@pytest.mark.parametrize("text", _CORPUS_B)
def test_corpus_b_is_byte_identical(text: str) -> None:
    new_text, conversions = format_bare_urls(text)
    assert new_text == text
    assert conversions == ()


# --- T023: Corpus C -- adversarial (15 rows) ------------------------------------


_CORPUS_C: list[tuple[str, str]] = [
    (
        "[a](<notes/Q3 (draft).md#note_1>)",
        "[a](<notes/Q3 (draft).md#note_1>)",
    ),
    (
        "[a](<notes/Q3 (draft).md#note_1> )",
        "[a](<notes/Q3 (draft).md#note_1> )",
    ),
    (
        "[a](<https://x.com/Q3 (draft>)",
        "[a](<https://x.com/Q3 (draft>)",
    ),
    (
        "```https://example.com/a\nbody\n```",
        "```https://example.com/a\nbody\n```",
    ),
    (
        "[[wiki]] https://example.com/a",
        "[[wiki]] [https://example.com/a](https://example.com/a)",
    ),
    (
        "[unclosed\n\nplain https://example.com/a\n",
        "[unclosed\n\nplain [https://example.com/a](https://example.com/a)\n",
    ),
    (
        "see ] https://example.com/a",
        "see ] [https://example.com/a](https://example.com/a)",
    ),
    (
        "see ( https://example.com/a",
        "see ( [https://example.com/a](https://example.com/a)",
    ),
    (
        "`[x]` then https://example.com/a",
        "`[x]` then [https://example.com/a](https://example.com/a)",
    ),
    (
        "[a](x.md#note_1) https://example.com/a [b](y.md#note_2)",
        "[a](x.md#note_1) [https://example.com/a](https://example.com/a) [b](y.md#note_2)",
    ),
    (
        "![i](p.png) https://example.com/a",
        "![i](p.png) [https://example.com/a](https://example.com/a)",
    ),
    (
        "text https://example.com/a <!-- id:task_a1b2 -->",
        "text [https://example.com/a](https://example.com/a) <!-- id:task_a1b2 -->",
    ),
    (
        "    https://example.com/a",
        "    [https://example.com/a](https://example.com/a)",
    ),
    (
        "end https://example.com/a\nnext line",
        "end [https://example.com/a](https://example.com/a)\nnext line",
    ),
    (
        "a https://example.com/a\nb\n",
        "a [https://example.com/a](https://example.com/a)\nb\n",
    ),
]

assert len(_CORPUS_C) == 15


@pytest.mark.parametrize(("text", "expected"), _CORPUS_C)
def test_adversarial_corpus_c_produces_the_exact_expected_result(text: str, expected: str) -> None:
    new_text, _conversions = format_bare_urls(text)
    assert new_text == expected


def test_adversarial_newline_count_is_unchanged() -> None:
    text = "a https://example.com/a\nb\n"
    new_text, _conversions = format_bare_urls(text)
    assert new_text.count("\n") == text.count("\n")


# --- T024: three-pass idempotency -- the single most important test here --------


@pytest.mark.parametrize("text", _CORPUS_A_TEXTS())
def test_idempotent_through_three_passes(text: str) -> None:
    """f(x) == f(f(x)) == f(f(f(x))), byte for byte, for every row of Corpus
    A. Three passes, not two: a defect that is stable at pass 2 but not
    pass 3 is exactly the compounding-corruption shape this guards against.
    Had the link mask (_mask_links) covered only a link's destination and
    not its text, pass 2 would yield `[[U](U)](U)` and pass 3
    `[[[U](U)](U)](U)` -- the file degrading a little on every save,
    silently, forever. Every subsequent save re-runs this transform over
    already-converted text, which is why this is the safety property and
    not a nicety."""
    once, _c1 = format_bare_urls(text)
    twice, c2 = format_bare_urls(once)
    thrice, c3 = format_bare_urls(twice)
    assert once == twice == thrice
    assert c2 == ()
    assert c3 == ()


# --- T025: the newline-count invariant, whole document --------------------------


def test_whole_document_newline_count_is_unchanged() -> None:
    """A document carrying frontmatter, a bare URL, a record link, a task
    mirror, a fenced code block, and a URL with balanced parens -- no mask
    or edit in this feature ever inserts or removes a newline, which is
    what keeps heal_text's warning line numbers, parse_tasks's task line
    numbers, and the editor's cursor row valid across a conversion."""
    text = (
        "---\n"
        "title: vendor comparison\n"
        "type: note\n"
        "created: 2026-07-30\n"
        "updated: 2026-07-30\n"
        "---\n"
        "\n"
        "See https://example.com/spec for details.\n"
        "\n"
        "[Q3 planning](../meetings/2026/07/q3-planning.md#meeting_20260728_a1b2c3d4)\n"
        "\n"
        "- [ ] call Terry <!-- id:task_a1b2 created:2026-07-30 -->\n"
        "\n"
        "```\n"
        "curl https://api.example.com/v1\n"
        "```\n"
        "\n"
        "Also see https://en.wikipedia.org/wiki/Foo_(bar) for background.\n"
    )
    new_text, conversions = format_bare_urls(text)
    assert new_text.count("\n") == text.count("\n")
    assert new_text.count("\r") == text.count("\r")
    assert len(conversions) == 2  # the bare URL and the wikipedia URL


# --- T028: the emphasis regression -----------------------------------------------


def test_emphasis_asterisks_stay_outside_the_link() -> None:
    """The corpus's first real failure (research R5): `*` was missing from
    the leading-boundary set, so `**https://example.com/a**` converted with
    the first `**` swallowed into the link text. Both asterisk pairs must
    land outside."""
    text = "**https://example.com/a**"
    new_text, conversions = format_bare_urls(text)
    assert new_text == "**[https://example.com/a](https://example.com/a)**"
    assert len(conversions) == 1
