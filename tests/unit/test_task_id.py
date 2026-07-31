from __future__ import annotations

import re

from endpaper.core.tasks import new_task_id


def test_format() -> None:
    task_id = new_task_id(())
    assert re.fullmatch(r"task_[0-9a-f]{4}", task_id)


def test_retries_on_collision(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import secrets

    calls = iter(["a1b2", "a1b2", "c3d4"])
    monkeypatch.setattr(secrets, "token_hex", lambda n: next(calls))

    task_id = new_task_id({"task_a1b2"})
    assert task_id == "task_c3d4"
