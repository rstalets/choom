from __future__ import annotations

from choom.tui.status_bar import BREADCRUMBS, in_flight_status, pick_breadcrumb


def test_pick_breadcrumb_is_a_member_of_the_tuple() -> None:
    for _ in range(50):
        assert pick_breadcrumb() in BREADCRUMBS


def test_in_flight_status_shows_the_breadcrumb_when_it_fits() -> None:
    text = in_flight_status("Boiling the ocean", width=80)
    assert text == "Boiling the ocean… — ctrl+c to cancel"


def test_in_flight_status_holds_the_same_phrase_for_the_life_of_one_request() -> None:
    breadcrumb = pick_breadcrumb()
    first = in_flight_status(breadcrumb, width=80)
    second = in_flight_status(breadcrumb, width=80)
    assert first == second


def test_narrow_width_drops_the_breadcrumb_whole_not_truncated() -> None:
    # "Running it up the flagpole" is the longest entry (26 chars); at 20 columns
    # nothing fits, and the fallback is the bare ellipsis -- never a partial phrase.
    text = in_flight_status("Running it up the flagpole", width=20)
    assert text == "⋯ — ctrl+c to cancel"
    assert "Running it up the fla" not in text


def test_cancel_hint_never_truncates_even_for_the_longest_breadcrumb() -> None:
    longest = max(BREADCRUMBS, key=len)
    fits = in_flight_status(longest, width=len(longest) + len("… — ctrl+c to cancel"))
    assert fits.endswith("— ctrl+c to cancel")
    too_narrow = in_flight_status(longest, width=len(longest))
    assert too_narrow == "⋯ — ctrl+c to cancel"
