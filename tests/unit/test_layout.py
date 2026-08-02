from __future__ import annotations

from choom.tui import layout


def test_min_vertical_screen_height_equals_eleven() -> None:
    assert layout.MIN_VERTICAL_SCREEN_HEIGHT == 11


def test_min_vertical_screen_height_equals_the_sum_of_its_five_components() -> None:
    # Pins the derivation, not just the value -- so it cannot silently drift
    # away from the sum it is supposed to be.
    assert layout.MIN_VERTICAL_SCREEN_HEIGHT == (
        layout.COLLECTION_BAR_ROWS
        + layout.STATUS_BAR_ROWS
        + layout.BAND_DIVIDER_ROWS
        + layout.MIN_UPPER_BAND_ROWS
        + layout.MIN_LOWER_BAND_ROWS
    )


def test_effective_orientation_vertical_falls_back_at_height_ten() -> None:
    assert layout.effective_orientation("vertical", 10) == "horizontal"


def test_effective_orientation_vertical_holds_at_height_eleven() -> None:
    assert layout.effective_orientation("vertical", 11) == "vertical"


def test_effective_orientation_horizontal_stays_horizontal_at_height_ten() -> None:
    assert layout.effective_orientation("horizontal", 10) == "horizontal"


def test_effective_orientation_horizontal_stays_horizontal_at_height_eleven() -> None:
    assert layout.effective_orientation("horizontal", 11) == "horizontal"


def test_effective_orientation_vertical_holds_at_a_comfortable_height() -> None:
    assert layout.effective_orientation("vertical", 24) == "vertical"
    assert layout.effective_orientation("vertical", 40) == "vertical"


def test_effective_orientation_unrecognised_stored_value_returns_horizontal() -> None:
    assert layout.effective_orientation("sideways", 40) == "horizontal"


def test_effective_orientation_never_raises_for_a_degenerate_height() -> None:
    assert layout.effective_orientation("vertical", 0) == "horizontal"
    assert layout.effective_orientation("horizontal", 0) == "horizontal"
