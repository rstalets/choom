from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main


def test_json_stdout_has_no_preamble_banner_or_trailing_text(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform"])
    capsys.readouterr()

    main(["meeting", "list", "--json"])
    out = capsys.readouterr().out

    assert out.startswith("[")
    assert out.rstrip("\n").endswith("]")

    records = json.loads(out)
    assert records[0]["title"] == "Q3 planning"
