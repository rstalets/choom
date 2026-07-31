from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Verb:
    name: str
    alias: str | None
    argument: str
    description: str


VERB_TABLE: tuple[Verb, ...] = (
    Verb("filter", "f", "<term>", "Narrow the list; no term clears it"),
    Verb("help", None, "", "Show this pane"),
    Verb("meeting", None, "<description>", "Create a meeting and open it for editing"),
    Verb("note", None, "<description>", "Create a note; with no description, today's daily note"),
    Verb("task", None, "<description>", "Add a task"),
    Verb("meetings", None, "", "Switch to the Meetings collection"),
    Verb("notes", None, "", "Switch to the Notes collection"),
    Verb("tasks", None, "", "Switch to the Tasks collection"),
    Verb("init", None, "", "Registered, no TUI action (reserved)"),
)

_BY_TOKEN: dict[str, Verb] = {}
for _verb in VERB_TABLE:
    _BY_TOKEN[_verb.name] = _verb
    if _verb.alias:
        _BY_TOKEN[_verb.alias] = _verb


def resolve_verb(stem: str) -> Verb | None:
    """Look up a verb by its name or alias (case-sensitive; callers lowercase first)."""
    return _BY_TOKEN.get(stem)
