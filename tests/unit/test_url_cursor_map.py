"""Unit tests for the cursor-offset mapping that follows a bare-URL
conversion (018-automatic-link-detection, contracts/core-api.md C2). Pure
integer arithmetic over `UrlConversion` records -- no text, no widget, no
terminal."""

from __future__ import annotations

from choom.core.links import map_cursor_offset
from choom.core.models import UrlConversion


def _conversion(start: int, end: int, url: str) -> UrlConversion:
    replacement = f"[{url}]({url})"
    return UrlConversion(start=start, end=end, url=url, replacement=replacement)


def test_empty_conversions_leaves_every_offset_unchanged() -> None:
    for offset in (0, 5, 1000):
        assert map_cursor_offset((), offset) == offset


def test_offset_before_a_conversion_is_unchanged() -> None:
    conv = _conversion(start=10, end=20, url="https://example.com")
    assert map_cursor_offset((conv,), 0) == 0
    assert map_cursor_offset((conv,), 9) == 9
    # Exactly at the conversion's start -- not yet "inside" it -- also
    # unchanged, since the cursor sits right before the new opening `[`.
    assert map_cursor_offset((conv,), 10) == 10


def test_offset_strictly_inside_a_conversion_lands_at_the_end_of_its_replacement() -> None:
    conv = _conversion(start=10, end=20, url="https://example.com")
    for offset in range(11, 20):
        assert map_cursor_offset((conv,), offset) == conv.start + len(conv.replacement)


def test_offset_after_a_conversion_is_shifted_by_what_it_added() -> None:
    conv = _conversion(start=10, end=20, url="https://example.com")
    growth = len(conv.replacement) - (conv.end - conv.start)
    assert map_cursor_offset((conv,), 20) == 20 + growth
    assert map_cursor_offset((conv,), 25) == 25 + growth


def test_multiple_conversions_accumulate_shift_in_order() -> None:
    first = _conversion(start=5, end=15, url="https://a.example")
    second = _conversion(start=25, end=35, url="https://b.example")
    conversions = (first, second)

    growth_first = len(first.replacement) - (first.end - first.start)
    growth_second = len(second.replacement) - (second.end - second.start)

    # Before both.
    assert map_cursor_offset(conversions, 0) == 0
    # Between the two, after the first only.
    assert map_cursor_offset(conversions, 20) == 20 + growth_first
    # Strictly inside the second.
    assert map_cursor_offset(conversions, 30) == (
        second.start + growth_first + len(second.replacement)
    )
    # After both.
    assert map_cursor_offset(conversions, 40) == 40 + growth_first + growth_second


def test_offset_at_the_very_end_of_the_original_span_equals_end_of_replacement() -> None:
    """The boundary case where "after" and "strictly inside" formulas
    coincide mathematically: at `end`, the shift formula and "land at the
    end of the replacement" formula produce the same offset."""
    conv = _conversion(start=10, end=20, url="https://example.com")
    assert map_cursor_offset((conv,), conv.end) == conv.start + len(conv.replacement)
