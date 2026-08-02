from __future__ import annotations

import json
from pathlib import Path

from choom.cli.main import main


def _assert_clean(text: str) -> None:
    assert "\x1b" not in text


def test_no_ansi_in_any_redirected_command_output(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    main(["init"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "list"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "list", "--json"])
    _assert_clean(capsys.readouterr().out)

    exit_code = main(["meeting", "list", "--since", "not-a-date"])
    assert exit_code == 2
    captured = capsys.readouterr()
    _assert_clean(captured.out)
    _assert_clean(captured.err)

    main(["note", "today"])
    _assert_clean(capsys.readouterr().out)

    main(["note", "new", "an idea", "--type", "idea", "--tag", "misc"])
    _assert_clean(capsys.readouterr().out)

    main(["note", "list"])
    _assert_clean(capsys.readouterr().out)

    main(["note", "list", "--json"])
    _assert_clean(capsys.readouterr().out)

    exit_code = main(["note", "list", "--since", "not-a-date"])
    assert exit_code == 2
    captured = capsys.readouterr()
    _assert_clean(captured.out)
    _assert_clean(captured.err)

    main(["task", "add", "buy milk", "--type", "errand", "--tag", "home"])
    _assert_clean(capsys.readouterr().out)

    main(["task", "list"])
    _assert_clean(capsys.readouterr().out)

    main(["task", "list", "--json"])
    _assert_clean(capsys.readouterr().out)

    (tmp_path / "tasks.md").write_text(
        (tmp_path / "tasks.md").read_text(encoding="utf-8") + "- [ ] broken <!-- id:\n",
        encoding="utf-8",
    )
    capsys.readouterr()
    exit_code = main(["task", "list", "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    _assert_clean(captured.out)
    _assert_clean(captured.err)

    exit_code = main(["task", "done", "no-such-id"])
    assert exit_code == 1
    captured = capsys.readouterr()
    _assert_clean(captured.out)
    _assert_clean(captured.err)


def test_no_ansi_across_remaining_subcommand_surface(tmp_path: Path, monkeypatch, capsys) -> None:
    """Extends the coverage above to the subcommands it does not yet reach
    (FR-016): `config assistant` (get and set), `links <id>`, `links check`,
    `links heal --dry-run`, `task show`, `task undone`, and the three
    `delete` verbs."""
    monkeypatch.chdir(tmp_path)

    main(["init"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform"])
    _assert_clean(capsys.readouterr().out)
    main(["meeting", "list", "--json"])
    meeting_id = json.loads(capsys.readouterr().out)[0]["id"]

    main(["note", "new", "an idea", "--type", "idea", "--tag", "misc"])
    _assert_clean(capsys.readouterr().out)
    main(["note", "list", "--json"])
    note_id = json.loads(capsys.readouterr().out)[0]["id"]

    main(["task", "add", "buy milk", "--type", "errand", "--tag", "home"])
    _assert_clean(capsys.readouterr().out)
    main(["task", "list", "--json"])
    task_id = json.loads(capsys.readouterr().out)[0]["id"]

    main(["config", "assistant"])
    _assert_clean(capsys.readouterr().out)

    main(["config", "assistant", "claude"])
    _assert_clean(capsys.readouterr().out)

    main(["links", task_id])
    _assert_clean(capsys.readouterr().out)

    main(["links", "check"])
    _assert_clean(capsys.readouterr().out)

    main(["links", "heal", "--dry-run"])
    _assert_clean(capsys.readouterr().out)

    main(["task", "show", task_id])
    _assert_clean(capsys.readouterr().out)

    main(["task", "undone", task_id])
    _assert_clean(capsys.readouterr().out)

    main(["task", "delete", task_id, "--force"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "delete", meeting_id, "--force"])
    _assert_clean(capsys.readouterr().out)

    main(["note", "delete", note_id, "--force"])
    _assert_clean(capsys.readouterr().out)


def test_no_ansi_when_main_refuses_a_non_tty_interface(monkeypatch, capsys) -> None:
    """US4 scenario 3: opening the interface with stdout redirected still
    refuses as it does today, and nothing but that refusal is written --
    no title sequence, on either stream (FR-015, FR-016)."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    exit_code = main([])

    assert exit_code != 0
    captured = capsys.readouterr()
    _assert_clean(captured.out)
    _assert_clean(captured.err)
