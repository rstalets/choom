from __future__ import annotations

from choom.core.models import EditorCommand, ParsedCommand, ReplyLine

EDITOR_COMMANDS: tuple[EditorCommand, ...] = (
    EditorCommand(
        name="ai",
        argument="<prompt>",
        description="Ask the configured assistant; the reply replaces this line",
        requires_argument=True,
    ),
    EditorCommand(
        name="link",
        argument="<search terms>",
        description="Insert a link to the matching record",
        requires_argument=True,
    ),
    EditorCommand(
        name="task",
        argument="<description>",
        description="Capture a task; this line becomes a link to it",
        requires_argument=True,
        accepts_suffix=True,
    ),
)

_BY_NAME: dict[str, EditorCommand] = {command.name: command for command in EDITOR_COMMANDS}


def parse_line(line: str) -> ParsedCommand | None:
    """Parse one submitted editor line as an in-editor command.

    Returns None when the line is ordinary document text -- which is every case except a
    line whose entire content is `/<registered word>[.<suffix>]` optionally followed by a
    space and argument text. Leading whitespace, a preceding character, an unregistered
    word, and a partial match all return None.

    The verb is split on the first `.` before the table lookup, mirroring
    `tui/command_bar.py`'s `resolve_mode`, so `/task.followup` and the command bar never
    disagree about what the suffix is. `ParsedCommand.suffix` is empty when there is no
    dot. A suffix on a command whose `accepts_suffix` is False still parses -- it is the
    dispatcher's job to reject it with a message, not this function's to discard it.

    Never raises: a line this cannot parse is a line the user typed, not an error.
    """
    if not line or line[0] != "/":
        return None
    rest = line.rstrip()[1:]
    word, _, argument = rest.partition(" ")
    stem, _, suffix = word.partition(".")
    command = _BY_NAME.get(stem.lower())
    if command is None:
        return None
    return ParsedCommand(command=command, argument=argument.strip(), suffix=suffix)


def parse_reply_lines(text: str) -> tuple[ReplyLine, ...]:
    """Classify every line of an assistant reply as prose or an eligible task command.

    Returns one `ReplyLine` per line of `text`, in order -- never dropped, merged, or
    reordered. A line is eligible (`task` is not `None`) when it has no leading
    whitespace and `parse_line` resolves it to a command named `task`, exactly the
    editor's own whole-line rule -- this delegates to `parse_line` rather than
    restating the grammar, so the editor and a reply can never disagree about what a
    task line is. `/task` with no description is still eligible; a `task` being
    unusable is `capture_task`'s concern, not this function's.

    Fence tracking (excluding a line inside a fenced code block from eligibility) is
    not yet implemented here -- see `capture_reply_tasks`'s caller and
    contracts/reply-capture.md §2; that arrives with US3.

    Pure: no workspace, no filesystem, no clock. Never raises.
    """
    result: list[ReplyLine] = []
    for line in text.splitlines():
        parsed = parse_line(line)
        task = parsed if parsed is not None and parsed.command.name == "task" else None
        result.append(ReplyLine(text=line, task=task))
    return tuple(result)
