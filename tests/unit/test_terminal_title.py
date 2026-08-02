from __future__ import annotations

import ctypes
import os

import pytest

from choom.tui.terminal_title import (
    CLEAR,
    POP,
    PUSH,
    SET,
    _enable_windows_vt,
    terminal_title,
)


class _FakeStream:
    """A fake `TextIO` with a controllable `isatty()` and controllable
    failures, so the emitter can be tested with no real terminal."""

    def __init__(
        self,
        isatty: bool = True,
        fail_write_at: int | None = None,
        fail_flush_at: int | None = None,
    ) -> None:
        self._isatty = isatty
        self.written: list[str] = []
        self.flush_count = 0
        self._fail_write_at = fail_write_at
        self._fail_flush_at = fail_flush_at

    def isatty(self) -> bool:
        return self._isatty

    def write(self, data: str) -> int:
        call_number = len(self.written) + 1
        if self._fail_write_at == call_number:
            raise OSError("simulated write failure")
        self.written.append(data)
        return len(data)

    def flush(self) -> None:
        self.flush_count += 1
        if self._fail_flush_at == self.flush_count:
            raise OSError("simulated flush failure")


class _FakeKernel32:
    def __init__(self, fail_get: bool = False, fail_set: bool = False) -> None:
        self._fail_get = fail_get
        self._fail_set = fail_set

    def GetStdHandle(self, which: int) -> int:  # noqa: N802 - Win32 API name
        return 1

    def GetConsoleMode(self, handle: int, mode_ref: object) -> int:  # noqa: N802
        return 0 if self._fail_get else 1

    def SetConsoleMode(self, handle: int, mode_value: int) -> int:  # noqa: N802
        return 0 if self._fail_set else 1


class _FakeWindll:
    def __init__(self, kernel32: _FakeKernel32) -> None:
        self.kernel32 = kernel32


# --- _enable_windows_vt (T006, E6) -----------------------------------------


def test_enable_windows_vt_returns_true_on_non_windows_without_touching_ctypes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(os, "name", "posix")

    class _ExplodingWindll:
        def __getattr__(self, name: str) -> object:
            raise AssertionError("ctypes.windll must not be touched on non-Windows")

    monkeypatch.setattr(ctypes, "windll", _ExplodingWindll(), raising=False)

    assert _enable_windows_vt() is True


def test_enable_windows_vt_returns_false_when_get_console_mode_fails(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(ctypes, "windll", _FakeWindll(_FakeKernel32(fail_get=True)), raising=False)

    assert _enable_windows_vt() is False


def test_enable_windows_vt_returns_false_when_set_console_mode_fails(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(ctypes, "windll", _FakeWindll(_FakeKernel32(fail_set=True)), raising=False)

    assert _enable_windows_vt() is False


def test_enable_windows_vt_returns_false_on_any_exception(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")

    class _ExplodingWindll:
        def __getattr__(self, name: str) -> object:
            raise RuntimeError("boom")

    monkeypatch.setattr(ctypes, "windll", _ExplodingWindll(), raising=False)

    assert _enable_windows_vt() is False


# --- terminal_title (T007, E1-E6) -------------------------------------------


def test_nothing_written_when_stream_is_not_a_tty() -> None:
    stream = _FakeStream(isatty=False)

    with terminal_title("choom — work-notes", stream=stream):
        pass

    assert stream.written == []


def test_enter_and_exit_bytes_are_exact_and_ordered() -> None:
    stream = _FakeStream(isatty=True)

    with terminal_title("choom — work-notes", stream=stream):
        pass

    # Asserted as an ordered sequence: a reversed POP/CLEAR would fail this.
    assert stream.written == [
        PUSH + SET.format(title="choom — work-notes"),
        CLEAR + POP,
    ]


def test_nothing_written_between_enter_and_exit() -> None:
    stream = _FakeStream(isatty=True)

    with terminal_title("choom — work-notes", stream=stream):
        assert stream.written == [PUSH + SET.format(title="choom — work-notes")]


def test_exit_bytes_written_when_block_raises_and_exception_propagates_unchanged() -> None:
    stream = _FakeStream(isatty=True)

    with pytest.raises(ValueError, match="boom"):
        with terminal_title("choom — work-notes", stream=stream):
            raise ValueError("boom")

    assert stream.written[-1] == CLEAR + POP


def test_write_failure_on_enter_is_swallowed_with_no_stderr(capsys) -> None:
    stream = _FakeStream(isatty=True, fail_write_at=1)

    with terminal_title("choom — work-notes", stream=stream):
        pass

    assert stream.written == []
    assert capsys.readouterr().err == ""


def test_flush_failure_on_enter_is_swallowed_with_no_stderr(capsys) -> None:
    stream = _FakeStream(isatty=True, fail_flush_at=1)

    with terminal_title("choom — work-notes", stream=stream):
        pass

    # Exit does nothing further, since enter never completed successfully.
    assert stream.written == [PUSH + SET.format(title="choom — work-notes")]
    assert capsys.readouterr().err == ""


def test_write_failure_on_exit_is_swallowed_and_does_not_change_what_block_does(
    capsys,
) -> None:
    stream = _FakeStream(isatty=True, fail_write_at=2)

    result = []
    with terminal_title("choom — work-notes", stream=stream):
        result.append("ran")

    assert result == ["ran"]
    assert stream.written == [PUSH + SET.format(title="choom — work-notes")]
    assert capsys.readouterr().err == ""


def test_flush_failure_on_exit_is_swallowed_and_exception_still_propagates(capsys) -> None:
    stream = _FakeStream(isatty=True, fail_flush_at=2)

    with pytest.raises(ValueError, match="boom"):
        with terminal_title("choom — work-notes", stream=stream):
            raise ValueError("boom")

    assert stream.written == [
        PUSH + SET.format(title="choom — work-notes"),
        CLEAR + POP,
    ]
    assert capsys.readouterr().err == ""


def test_nothing_written_on_exit_when_windows_vt_was_unavailable(monkeypatch) -> None:
    import choom.tui.terminal_title as terminal_title_module

    monkeypatch.setattr(terminal_title_module, "_enable_windows_vt", lambda: False)
    stream = _FakeStream(isatty=True)

    with terminal_title("choom — work-notes", stream=stream):
        pass

    assert stream.written == []
