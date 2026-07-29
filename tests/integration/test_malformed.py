from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main


def test_malformed_file_is_skipped_warned_and_left_byte_identical(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning", "--type", "standup"])
    capsys.readouterr()

    broken = tmp_path / "meetings" / "2026-07-28-broken.md"
    broken.write_text("---\nid: broken\n", encoding="utf-8")
    before = broken.read_bytes()

    exit_code = main(["meeting", "list", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    records = json.loads(captured.out)
    assert len(records) == 1
    assert records[0]["title"] == "Q3 planning"

    assert "broken" in captured.err

    after = broken.read_bytes()
    assert before == after
