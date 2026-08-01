from __future__ import annotations

import pytest

from choom.core.text import matches_terms

# Regression: a multi-word query used to be tested as one contiguous substring,
# so "research Okta" matched nothing even when a note titled "Okta rollout" of
# type "research" existed. Both words are present; they are simply not adjacent.


@pytest.mark.parametrize(
    "query,expected",
    [
        ("research", True),
        ("okta", True),
        ("research okta", True),
        ("okta research", True),
        ("OKTA Research", True),
        ("research okta missing", False),
        ("", True),
        ("   ", True),
    ],
)
def test_every_term_must_appear_in_any_order(query: str, expected: bool) -> None:
    assert matches_terms("Okta rollout research platform", query) is expected


def test_a_single_term_still_behaves_as_a_plain_substring() -> None:
    assert matches_terms("Okta rollout", "kta roll")
    assert not matches_terms("Okta rollout", "rolloutx")
