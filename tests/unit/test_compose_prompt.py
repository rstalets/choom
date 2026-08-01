from __future__ import annotations

from pathlib import Path

from choom.core.assistants import compose_prompt

_INSTRUCTION_CLAUSES = [
    "Answer directly. No preamble, no restating the question, no sign-off.",
    "Do not wrap the whole reply in a",
    "code fence unless the entire answer is code.",
    "Match the length to the request. These are working notes, not a report.",
    "You cannot ask a question.",
    "The request may refer to the document by position",
    "Do not edit any file.",
]


def test_composed_prompt_contains_document_path_and_line_number(tmp_path: Path) -> None:
    document = tmp_path / "note.md"
    composed = compose_prompt("summarise this", document, 12)
    assert str(document) in composed
    assert "line 12" in composed


def test_composed_prompt_contains_every_instruction_clause(tmp_path: Path) -> None:
    composed = compose_prompt("anything", tmp_path / "note.md", 1)
    for clause in _INSTRUCTION_CLAUSES:
        assert clause in composed


def test_users_prompt_is_last(tmp_path: Path) -> None:
    composed = compose_prompt("the user's exact words", tmp_path / "note.md", 3)
    assert composed.rstrip().endswith("the user's exact words")
