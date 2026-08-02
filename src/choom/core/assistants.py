from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path, PurePosixPath

from choom.core.models import AssistantProfile, AssistantReply, ResolvedAssistant

_INSTRUCTIONS = """\
You are answering a request from inside a plain-text notes editor. Your reply is
inserted directly into the user's document, replacing the line they typed. They
do not see it anywhere first.

- Answer directly. No preamble, no restating the question, no sign-off, and no
  narration of what you're about to do. You may need to read the file first to
  resolve a position reference -- do that silently and start your reply with
  the answer itself, not a sentence announcing the read. For example, if asked
  to summarize the lines above, the reply must begin with the summary, never
  with something like "I'll read the file to see what's above" or "Let me
  check the lines above first."
- Write markdown that belongs in working notes: prose, a list, a table, or a
  fenced diagram, whichever suits the answer. Do not wrap the whole reply in a
  code fence unless the entire answer is code.
- Match the length to the request. These are working notes, not a report.
- You cannot ask a question. Nothing here is interactive and there is no second
  turn. If the request is ambiguous, take the most reasonable reading, answer it,
  and note the assumption in one short line.
- The request may refer to the document by position -- "the paragraph above",
  "this section", "everything below". Read the file and resolve those against the
  line number given below.
- Do not edit any file. The document is open in an editor whose unsaved buffer
  overwrites the file on the next save, so any edit you make is discarded."""


def _claude_build_args(prompt: str) -> list[str]:
    # Read-only: the composed prompt tells the assistant to read the saved document to
    # resolve positional references (FR-009), which the CLI's default permission mode
    # would otherwise silently deny -- there's no TTY in `-p` mode to approve it. Nothing
    # beyond Read is granted, reinforcing FR-018 ("do not edit any file") at the
    # permission level rather than leaving it to the instructions alone.
    return ["-p", prompt, "--allowedTools", "Read"]


def _copilot_build_args(prompt: str) -> list[str]:
    # Same reasoning as _claude_build_args, in Copilot CLI's flag shape. `--output-format
    # json` switches stdout to JSONL events instead of Copilot's default text mode, which
    # mixes tool-call status lines and a stats footer into the reply -- see
    # _copilot_parse_reply for why that structure is needed (#69).
    return ["-p", prompt, "--allow-tool", "read", "--output-format", "json"]


def _claude_parse_reply(stdout: str) -> str:
    return stdout


def _copilot_parse_reply(stdout: str) -> str:
    """Pull the final answer out of Copilot's `--output-format json` event stream.

    Each assistant turn is one "assistant.message" event. A turn that also requests a
    tool call carries the model's narration of that call in the same `content` field --
    e.g. "I'll read the file to check what's above" -- and no instruction wording tested
    reliably suppressed it (#69), so narration turns are identified structurally instead:
    they're the ones with a non-empty `toolRequests` list. The terminal turn, the last one
    with none, holds the actual reply.
    """
    reply = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant.message":
            continue
        data = event.get("data") or {}
        if data.get("toolRequests"):
            continue
        reply = data.get("content", "")
    return reply


PROFILES: tuple[AssistantProfile, ...] = (
    AssistantProfile(
        name="claude",
        display_name="Claude Code CLI",
        binary="claude",
        build_args=_claude_build_args,
        parse_reply=_claude_parse_reply,
        # A user-scope skill: read every session, any working directory (research R1).
        discovery_relpath=PurePosixPath(".claude/skills/choom/SKILL.md"),
    ),
    AssistantProfile(
        name="copilot",
        display_name="GitHub Copilot CLI",
        binary="copilot",
        build_args=_copilot_build_args,
        parse_reply=_copilot_parse_reply,
        # Copilot CLI's documented "user-level instructions across all repositories"
        # location (research R2).
        discovery_relpath=PurePosixPath(".copilot/skills/choom/SKILL.md"),
    ),
)

_BY_NAME: dict[str, AssistantProfile] = {profile.name: profile for profile in PROFILES}


def available_assistants() -> tuple[str, ...]:
    """Return the names of supported assistants runnable on this machine, sorted.

    Uses shutil.which, so PATHEXT resolves `claude.cmd` / `claude.exe` on Windows.
    Launches nothing; cannot hang. Returns an empty tuple when none are installed.
    """
    return tuple(sorted(profile.name for profile in PROFILES if shutil.which(profile.binary)))


def resolve_assistant(configured: str | None) -> ResolvedAssistant:
    """Decide which assistant `/ai` should call.

    `configured` is the stored setting, or None when unset. A configured name is used as
    given. "none" resolves to nothing and does NOT fall back to detection. When unset,
    detection decides: exactly one available assistant is used; two or more is reported
    as ambiguous rather than resolved by precedence; none available is reported as unset.

    Never raises. An unrecognised `configured` value is treated as unset.
    """
    available = available_assistants()

    if configured == "none":
        return ResolvedAssistant(profile=None, source="none", available=available)

    if configured is not None:
        profile = _BY_NAME.get(configured)
        if profile is not None:
            return ResolvedAssistant(profile=profile, source="configured", available=available)
        # Unrecognised value: fall through to detection, treated as unset.

    if len(available) == 1:
        return ResolvedAssistant(
            profile=_BY_NAME[available[0]], source="detected", available=available
        )
    if len(available) >= 2:
        return ResolvedAssistant(profile=None, source="ambiguous", available=available)
    return ResolvedAssistant(profile=None, source="unset", available=available)


def compose_prompt(user_prompt: str, document: Path, line: int) -> str:
    """Build the text handed to the assistant.

    Prepends the instructions required by FR-010 -- that the reply is inserted directly
    into a working-notes editor, that it should answer directly in a form suited to that
    medium, that it cannot ask a question, and that it should reply rather than edit the
    file -- then names the saved document and the position of the request within it.

    `line` is the 1-based line number of the `/ai` line in the file as saved, counted over
    the whole file including frontmatter, so the assistant can resolve positional requests
    like "the paragraph above" or "lines 15-18" (FR-009).
    """
    return (
        f"{_INSTRUCTIONS}\n\n"
        f"The user's document has just been saved to:\n"
        f"  {document}\n\n"
        f"The request is on line {line} of that file. Content above that line comes before it\n"
        f"in the document; content below comes after.\n\n"
        f"{user_prompt}"
    )


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n")
    if text.endswith("\n"):
        text = text[:-1]
    return text


def _last_stderr_line(stderr: str) -> str:
    lines = [line for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else ""


class AssistantRequest:
    """One in-flight assistant invocation.

    Owns the child process. wait() blocks until it exits; cancel() terminates it, which
    is what unblocks a waiting caller -- Textual thread workers cannot be interrupted
    mid-call, so killing the process is the cancellation mechanism, not an optimisation.
    """

    def __init__(
        self,
        profile: AssistantProfile,
        process: subprocess.Popen[str] | None,
        spawn_error: str,
    ) -> None:
        self.profile = profile
        self._process = process
        self._spawn_error = spawn_error
        self._cancel_requested = False

    def wait(self) -> AssistantReply:
        """Block until the assistant exits and return what it produced.

        Never raises. Non-zero exit, empty output, a missing binary, and cancellation all
        come back as an AssistantReply with ok=False.
        """
        if self._process is None:
            return AssistantReply(ok=False, text="", message=self._spawn_error, cancelled=False)

        stdout, stderr = self._process.communicate()

        if self._cancel_requested:
            return AssistantReply(ok=False, text="", message="", cancelled=True)

        if self._process.returncode != 0:
            last_line = _last_stderr_line(stderr)
            message = (
                f"{self.profile.display_name} failed: {last_line}"
                if last_line
                else f"{self.profile.display_name} failed"
            )
            return AssistantReply(ok=False, text="", message=message, cancelled=False)

        text = _normalise(self.profile.parse_reply(stdout))
        if not text.strip():
            return AssistantReply(
                ok=False,
                text="",
                message=f"{self.profile.display_name} returned an empty reply",
                cancelled=False,
            )

        return AssistantReply(ok=True, text=text, message="", cancelled=False)

    def cancel(self) -> None:
        """Terminate the child process group.

        Idempotent and safe after the process has already exited -- a request that
        finishes microseconds before the user presses ctrl+c must not raise.
        """
        if self._process is None or self._process.poll() is not None:
            return
        self._cancel_requested = True
        try:
            if sys.platform == "win32":
                self._process.terminate()
            else:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass


def start_request(
    profile: AssistantProfile,
    prompt: str,
    *,
    cwd: Path,
) -> AssistantRequest:
    """Spawn the assistant and return a handle immediately.

    The child is launched in its own process group with stdin at DEVNULL and stdout and
    stderr captured, so an assistant that tried to prompt gets EOF and exits rather than
    hanging invisibly.

    Never raises: a binary that is missing or cannot be spawned yields a handle whose
    wait() returns a failed AssistantReply naming the problem.
    """
    args = [profile.binary, *profile.build_args(prompt)]

    try:
        if sys.platform == "win32":
            process = subprocess.Popen(
                args,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            process = subprocess.Popen(
                args,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=True,
            )
    except FileNotFoundError:
        return AssistantRequest(
            profile, None, f"{profile.display_name} is not installed or not on your PATH"
        )
    except OSError as exc:
        return AssistantRequest(profile, None, f"could not start {profile.display_name}: {exc}")

    return AssistantRequest(profile, process, "")
