from __future__ import annotations

import re

from choom.core.models import EditorCommand, ParsedCommand, ReplyLine

# CommonMark fence rule: three or more backticks or tildes, after at most three
# leading spaces, with an optional info string that plays no role here.
_FENCE_OPEN = re.compile(r"^ {0,3}(?P<char>`{3,}|~{3,})")

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
        description="Insert a link to the matching record, or choose one when several match",
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
    reordered. A line is eligible (`task` is not `None`) when all of these hold: it is
    not inside a fenced code block, it has no leading whitespace, and `parse_line`
    resolves it to a command named `task` -- the last two are exactly the editor's own
    whole-line rule, and this delegates to `parse_line` rather than restating the
    grammar, so the editor and a reply can never disagree about what a task line is.
    `/task` with no description is still eligible; a `task` being unusable is
    `capture_task`'s concern, not this function's.

    A fence opens on a line whose first non-space run (after at most three leading
    spaces) is three or more backticks or three or more tildes, with or without an
    info string, and closes on a later line using the same character, at least as
    long, with no info string (contracts/reply-capture.md §2). A fence that is never
    closed puts every remaining line inside it -- the safe direction. A four-space
    indented code block needs no separate handling: the leading-whitespace rule
    already excludes it.

    Pure: no workspace, no filesystem, no clock. Never raises.
    """
    result: list[ReplyLine] = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line in text.splitlines():
        match = _FENCE_OPEN.match(line)

        if in_fence:
            if (
                match is not None
                and match.group("char")[0] == fence_char
                and len(match.group("char")) >= fence_len
                and line[match.end() :].strip() == ""
            ):
                in_fence = False
            result.append(ReplyLine(text=line, task=None))
            continue

        if match is not None:
            in_fence = True
            fence_char = match.group("char")[0]
            fence_len = len(match.group("char"))
            result.append(ReplyLine(text=line, task=None))
            continue

        parsed = parse_line(line)
        task = parsed if parsed is not None and parsed.command.name == "task" else None
        result.append(ReplyLine(text=line, task=task))

    return tuple(result)
