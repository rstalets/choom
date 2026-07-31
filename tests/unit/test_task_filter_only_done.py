from __future__ import annotations

from datetime import date

from endpaper.core.models import Task, TaskFilter
from endpaper.core.tasks import filter_tasks


def _task(text: str, *, done: bool) -> Task:
    return Task(id=None, text=text, done=done, type="", tags=(), created=date(2026, 1, 1), line=0)


def test_open_only_is_the_unchanged_default() -> None:
    tasks = [_task("open", done=False), _task("done", done=True)]
    result = filter_tasks(tasks, TaskFilter())
    assert [t.text for t in result] == ["open"]


def test_include_done_returns_everything() -> None:
    tasks = [_task("open", done=False), _task("done", done=True)]
    result = filter_tasks(tasks, TaskFilter(include_done=True))
    assert {t.text for t in result} == {"open", "done"}


def test_only_done_returns_completed_only() -> None:
    tasks = [_task("open", done=False), _task("done", done=True)]
    result = filter_tasks(tasks, TaskFilter(only_done=True))
    assert [t.text for t in result] == ["done"]


def test_only_done_wins_over_include_done() -> None:
    tasks = [_task("open", done=False), _task("done", done=True)]
    result = filter_tasks(tasks, TaskFilter(only_done=True, include_done=True))
    assert [t.text for t in result] == ["done"]
