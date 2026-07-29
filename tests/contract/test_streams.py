from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main


def test_scan_warnings_go_to_stderr_and_stdout_stays_clean_json(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning"])
    capsys.readouterr()

    (tmp_path / "meetings" / "broken.md").write_text("not frontmatter at all", encoding="utf-8")

    exit_code = main(["meeting", "list", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    records = json.loads(captured.out)
    assert len(records) == 1

    assert captured.err != ""
    assert "broken.md" in captured.err
