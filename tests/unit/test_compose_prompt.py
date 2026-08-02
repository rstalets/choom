from __future__ import annotations

from pathlib import Path

from choom.core.assistants import PROFILES, compose_prompt

_INSTRUCTION_CLAUSES = [
    "Answer directly. No preamble, no restating the question, no sign-off, and no",
    "narration of what you're about to do.",
    "Do not wrap the whole reply in a",
    "code fence unless the entire answer is code.",
    "Match the length to the request. These are working notes, not a report.",
    "You cannot ask a question.",
    "The request may refer to the document by position",
    "Do not edit any file.",
]


def test_composed_prompt_contains_document_path_and_line_number(tmp_path: Path) -> None:
    document = tmp_path / "note.md"
    composed = compose_prompt("summarise this", document, 12, task_capture=True)
    assert str(document) in composed
    assert "line 12" in composed


def test_composed_prompt_contains_every_instruction_clause(tmp_path: Path) -> None:
    composed = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=True)
    for clause in _INSTRUCTION_CLAUSES:
        assert clause in composed


def test_users_prompt_is_last(tmp_path: Path) -> None:
    composed = compose_prompt("the user's exact words", tmp_path / "note.md", 3, task_capture=True)
    assert composed.rstrip().endswith("the user's exact words")


def test_task_syntax_clause_present_when_task_capture_is_true(tmp_path: Path) -> None:
    composed = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=True)
    assert "/task" in composed
    assert "#tags" in composed


def test_task_syntax_clause_directs_rather_than_merely_permits(tmp_path: Path) -> None:
    """The first wording explained the syntax and closed with "this is optional --
    most replies need none", while an earlier instruction recommends "a list". Asked
    for the action items, a real assistant read those together and returned a plain
    markdown list every time -- the syntax reached it and went unused. The clause has
    to say which shape wins for content that is a thing to be done."""
    composed = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=True)
    assert "not as\n  a bullet in a markdown list" in composed
    assert "overrides the guidance above" in composed
    assert "optional" not in composed


def test_task_syntax_clause_bounds_capture_to_what_was_asked(tmp_path: Path) -> None:
    """The directive wording, on its own, made a plain "summarise this" request
    append captured tasks nobody asked for -- real records the user then has to go
    and delete."""
    composed = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=True)
    assert "Answer only what was asked" in composed
    assert "never a\n  list of captured tasks appended to it" in composed


def test_task_syntax_clause_tells_the_assistant_to_fence_its_examples(tmp_path: Path) -> None:
    """Asked how the syntax works, a real assistant wrote its example unfenced, which
    the classifier would have captured as two real tasks. The classifier's fence rule
    only helps if the assistant fences."""
    composed = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=True)
    assert "put every example inside a code\n  fence" in composed


def test_task_syntax_clause_absent_when_task_capture_is_false(tmp_path: Path) -> None:
    with_clause = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=True)
    without_clause = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=False)
    assert "/task" not in without_clause
    assert without_clause != with_clause


def test_task_capture_false_is_byte_identical_to_the_prompt_without_the_flag(
    tmp_path: Path,
) -> None:
    # There is no third state -- omitting the flag is not a valid call any more
    # (it is required and keyword-only) -- so this pins task_capture=False against
    # the instruction block that predates the feature, via the clause list above.
    composed = compose_prompt("anything", tmp_path / "note.md", 1, task_capture=False)
    for clause in _INSTRUCTION_CLAUSES:
        assert clause in composed
    assert "/task" not in composed


def test_task_syntax_clause_is_identical_across_every_profile() -> None:
    # The clause is one constant, appended verbatim regardless of which assistant
    # is configured -- compose_prompt takes no profile argument at all, so the
    # only way this could vary is if a future change threaded one through. This
    # locks the two live profiles both produce the same clause text.
    prompts = {
        profile.name: compose_prompt("anything", Path("note.md"), 1, task_capture=True)
        for profile in PROFILES
    }
    texts = list(prompts.values())
    assert all(text == texts[0] for text in texts)
