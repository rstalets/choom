from __future__ import annotations

import json

_REPORT_KEYS = {"file", "line", "text", "target_id", "old_path", "new_path", "status"}


def test_links_id_json_direction_both_has_id_out_in_keys(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    target_id = json.loads(cli("meeting", "list", "--json").out)[0]["id"]

    result = cli("links", target_id, "--json")
    assert result.exit_code == 0
    payload = json.loads(result.out)
    assert set(payload.keys()) == {"id", "out", "in"}
    assert payload["id"] == target_id
    assert isinstance(payload["out"], list)
    assert isinstance(payload["in"], list)


def test_links_id_direction_out_and_in_return_bare_arrays(cli) -> None:
    cli("meeting", "new", "x")
    target_id = json.loads(cli("meeting", "list", "--json").out)[0]["id"]

    out_result = cli("links", target_id, "--json", "--direction", "out")
    assert out_result.exit_code == 0
    assert isinstance(json.loads(out_result.out), list)

    in_result = cli("links", target_id, "--json", "--direction", "in")
    assert in_result.exit_code == 0
    assert isinstance(json.loads(in_result.out), list)


def test_links_id_report_schema_has_exactly_seven_keys(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    meeting = json.loads(cli("meeting", "list", "--json").out)[0]
    cli("note", "new", "vendor landscape")
    note_path = json.loads(cli("note", "list", "--json").out)[0]["path"]

    text = (cli.root / note_path).read_text(encoding="utf-8")
    (cli.root / note_path).write_text(
        text + f"\nSee [Q3](wrong.md#{meeting['id']}).\n", encoding="utf-8"
    )

    result = cli("links", meeting["id"], "--json", "--direction", "in")
    assert result.exit_code == 0
    records = json.loads(result.out)
    assert len(records) == 1
    assert set(records[0].keys()) == _REPORT_KEYS


def test_links_id_empty_result_exits_0(cli) -> None:
    cli("meeting", "new", "nothing points here")
    meeting_id = json.loads(cli("meeting", "list", "--json").out)[0]["id"]

    result = cli("links", meeting_id, "--json")
    assert result.exit_code == 0
    payload = json.loads(result.out)
    assert payload["out"] == []
    assert payload["in"] == []


def test_links_unresolvable_id_exits_1(cli) -> None:
    result = cli("links", "meeting_00000000_deadbeef")
    assert result.exit_code == 1
    assert result.err != ""


def test_links_bad_direction_exits_2(cli) -> None:
    cli("meeting", "new", "x")
    meeting_id = json.loads(cli("meeting", "list", "--json").out)[0]["id"]
    result = cli("links", meeting_id, "--direction", "sideways")
    assert result.exit_code == 2


def test_links_table_output_is_tab_separated_no_header(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    meeting = json.loads(cli("meeting", "list", "--json").out)[0]
    cli("note", "new", "vendor landscape")
    note_path = json.loads(cli("note", "list", "--json").out)[0]["path"]
    text = (cli.root / note_path).read_text(encoding="utf-8")
    (cli.root / note_path).write_text(text + f"\nSee [Q3](#{meeting['id']}).\n", encoding="utf-8")

    result = cli("links", meeting["id"], "--direction", "in")
    assert result.exit_code == 0
    lines = result.out.splitlines()
    assert len(lines) == 1
    fields = lines[0].split("\t")
    assert len(fields) == 4


def test_links_stdout_stderr_never_interleaved(cli) -> None:
    result = cli("links", "meeting_00000000_deadbeef", "--json")
    assert result.exit_code == 1
    # stdout carries nothing on the not-found path; the message is on stderr only
    assert result.out == ""
    assert "meeting_00000000_deadbeef" in result.err


# --- check / heal --------------------------------------------------------------


def test_links_check_reports_stale_and_dead_distinctly(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    meeting = json.loads(cli("meeting", "list", "--json").out)[0]
    cli("note", "new", "vendor landscape")
    note_path = json.loads(cli("note", "list", "--json").out)[0]["path"]

    text = (cli.root / note_path).read_text(encoding="utf-8")
    stale = f"[stale](wrong.md#{meeting['id']})\n"
    dead = "[dead](#meeting_00000000_deadbeef)\n"
    (cli.root / note_path).write_text(text + "\n" + stale + dead, encoding="utf-8")

    result = cli("links", "check", "--json")
    assert result.exit_code == 1
    records = json.loads(result.out)
    statuses = {r["status"] for r in records}
    assert statuses == {"stale", "dead"}


def test_links_check_clean_workspace_exits_0(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    result = cli("links", "check", "--json")
    assert result.exit_code == 0
    assert json.loads(result.out) == []


def test_links_heal_dry_run_is_non_blocking_and_write_free(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    meeting = json.loads(cli("meeting", "list", "--json").out)[0]
    cli("note", "new", "vendor landscape")
    note_path = json.loads(cli("note", "list", "--json").out)[0]["path"]

    text = (cli.root / note_path).read_text(encoding="utf-8")
    (cli.root / note_path).write_text(
        text + f"\n[stale](wrong.md#{meeting['id']})\n", encoding="utf-8"
    )
    before = (cli.root / note_path).read_bytes()

    result = cli("links", "heal", "--dry-run", "--json")
    assert result.exit_code == 1
    after = (cli.root / note_path).read_bytes()
    assert before == after


def test_links_report_json_schema(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    meeting = json.loads(cli("meeting", "list", "--json").out)[0]
    cli("note", "new", "vendor landscape")
    note_path = json.loads(cli("note", "list", "--json").out)[0]["path"]
    text = (cli.root / note_path).read_text(encoding="utf-8")
    (cli.root / note_path).write_text(
        text + f"\n[stale](wrong.md#{meeting['id']})\n", encoding="utf-8"
    )

    result = cli("links", "check", "--json")
    records = json.loads(result.out)
    assert len(records) == 1
    assert set(records[0].keys()) == _REPORT_KEYS
    assert records[0]["old_path"] == "wrong.md"
    assert records[0]["new_path"] is not None
