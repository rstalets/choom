"""T030 (020-vertical-tui-mode, Polish): FR-020's "no residual difference"
in horizontal, made executable rather than left as review advice.

Parses `app.tcss` into selector -> declarations and asserts that the base
rules for `#body`, `#scope-pane`, `#list-pane`, and `#preview-pane`, plus
every selector contracts/layout.md's "must not change" list names, are
*exactly* what they were before this feature. A failure here means either
scope creep in a later change, or a deliberate edit that has to be
re-recorded here on purpose -- this file is the record, not a guess.
"""

from __future__ import annotations

import re
from pathlib import Path

_APP_TCSS = Path(__file__).parents[2] / "src" / "choom" / "tui" / "app.tcss"


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _parse_rules(text: str) -> dict[str, dict[str, str]]:
    """selector -> {declaration-key: declaration-value}, in the exact form
    each rule's own block writes it (no unit conversion, no normalisation
    beyond stripping whitespace) -- a change to a value's spelling, not just
    its meaning, is exactly the kind of drift this test exists to catch."""
    text = _strip_comments(text)
    rules: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selector = match.group(1).strip()
        decls: dict[str, str] = {}
        for line in match.group(2).strip().splitlines():
            line = line.strip().rstrip(";")
            if not line:
                continue
            key, _, value = line.partition(":")
            decls[key.strip()] = value.strip()
        rules[selector] = decls
    return rules


#: The base rules this feature's own contract (contracts/layout.md) commits
#: to leaving untouched -- every vertical-only change is an *added* selector
#: (`#body.-vertical`, `#body.-vertical #list-pane`, etc.), never an edit to
#: these.
_PROTECTED_BASE_RULES: dict[str, dict[str, str]] = {
    "#body": {"height": "1fr", "layout": "horizontal"},
    "#scope-pane": {"width": "14", "border-right": "solid $accent"},
    "#list-pane": {"width": "2fr", "border-right": "solid $accent"},
    "#preview-pane": {"width": "3fr", "padding": "0 1"},
}

#: Every selector contracts/layout.md's "must not change" list names --
#: outside this feature's blast radius entirely, appearing in the diff would
#: be scope creep on its own terms.
_PROTECTED_UNRELATED_RULES: dict[str, dict[str, str]] = {
    "Screen": {"layout": "vertical"},
    "CollectionBar": {"dock": "top", "height": "1", "background": "$panel"},
    "#scope-list": {"height": "1fr"},
    "#list-header": {"height": "1", "background": "$panel", "text-style": "bold"},
    "#meeting-list": {"height": "1fr"},
    "#bottom-bar": {"dock": "bottom", "height": "auto"},
    "CommandBar": {"height": "1", "display": "none"},
    "CommandBar #bar-row": {"height": "1"},
    "CommandBar #bar-prefix": {"width": "1", "color": "$accent"},
    "CommandBar Input": {"height": "1", "border": "none", "padding": "0"},
    "StatusBar": {"height": "1", "background": "$panel"},
    "#link-picker": {"height": "auto", "max-height": "8", "border-top": "solid $accent"},
    "#links-section": {"height": "auto", "max-height": "12", "border-top": "solid $accent"},
    "#links-list": {"height": "auto", "max-height": "10"},
    "#preview-links-list": {"height": "auto", "max-height": "10"},
    "#editor": {"height": "1fr", "width": "1fr"},
    "EditorPane": {"height": "1fr", "width": "1fr"},
    "#confirm-dialog": {
        "width": "auto",
        "height": "auto",
        "padding": "1 2",
        "background": "$panel",
        "border": "thick $accent",
        "align": "center middle",
    },
    "ConfirmDialog": {"align": "center middle"},
    "HelpScreen": {"align": "center middle", "background": "$background 60%"},
    "#help-pane": {
        "dock": "bottom",
        "height": "60%",
        "width": "100%",
        "background": "$panel",
        "border-top": "thick $accent",
        "padding": "1 2",
    },
    "#help-body": {"height": "1fr"},
}


def test_base_body_scope_list_preview_rules_are_unchanged() -> None:
    rules = _parse_rules(_APP_TCSS.read_text(encoding="utf-8"))
    for selector, expected in _PROTECTED_BASE_RULES.items():
        assert selector in rules, f"{selector} is missing from app.tcss entirely"
        assert rules[selector] == expected, f"{selector} has drifted from its recorded form"


def test_unrelated_selectors_are_unchanged() -> None:
    rules = _parse_rules(_APP_TCSS.read_text(encoding="utf-8"))
    for selector, expected in _PROTECTED_UNRELATED_RULES.items():
        assert selector in rules, f"{selector} is missing from app.tcss entirely"
        assert rules[selector] == expected, f"{selector} has drifted from its recorded form"


def test_every_protected_selector_still_exists_and_is_not_duplicated() -> None:
    """A selector appearing twice (e.g. accidentally re-declared) would let
    the *second* declaration silently win in CSS, defeating the point of
    locking the first -- the parser above would also just overwrite the
    first occurrence in the dict, masking the duplication. Guard against
    that directly by counting raw selector-line occurrences in the source."""
    text = _strip_comments(_APP_TCSS.read_text(encoding="utf-8"))
    for selector in {**_PROTECTED_BASE_RULES, **_PROTECTED_UNRELATED_RULES}:
        # Anchored to the start of a line (ignoring leading whitespace): a
        # bare `#list-pane` and the compound `#body.-vertical #list-pane`
        # both contain the literal substring "#list-pane {", so an
        # unanchored search would double-count the base selector every time
        # a vertical-only variant of it exists.
        pattern = r"(?:^|\n)[ \t]*" + re.escape(selector) + r"\s*\{"
        occurrences = len(re.findall(pattern, text))
        assert occurrences == 1, f"{selector} appears {occurrences} times, expected exactly 1"
