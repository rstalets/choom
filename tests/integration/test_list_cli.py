from __future__ import annotations

import json

import pytest

EXPECTED_NOTE_KEYS = {"id", "path", "title", "type", "tags", "created", "updated"}


def test_json_output_is_an_array_of_objects(cli) -> None:
    cli("meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform")

    r = cli("meeting", "list", "--json")
    assert r.exit_code == 0

    records = json.loads(r.out)
    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["title"] == "Q3 planning"


def test_json_output_has_seven_key_schema(cli) -> None:
    cli("note", "new", "vendor landscape", "--type", "research", "--tag", "procurement")

    r = cli("note", "list", "--json")
    assert r.exit_code == 0

    records = json.loads(r.out)
    assert len(records) == 1
    assert set(records[0].keys()) == EXPECTED_NOTE_KEYS


@pytest.mark.parametrize(
    ("noun", "kind", "other_kind"),
    [
        ("meeting", "standup", "vendor"),
        ("note", "research", "idea"),
    ],
)
def test_filters_combine_conjunctively(cli, noun: str, kind: str, other_kind: str) -> None:
    cli(noun, "new", f"{kind} one", "--type", kind, "--tag", "platform")
    cli(noun, "new", f"{kind} two", "--type", kind, "--tag", "legal")
    cli(noun, "new", f"{other_kind} item", "--type", other_kind, "--tag", "platform")

    r = cli(noun, "list", "--json", "--type", kind, "--tag", "platform")
    records = json.loads(r.out)

    assert len(records) == 1
    assert records[0]["title"] == f"{kind} one"


def test_since_is_inclusive_and_filters_by_created_date(cli) -> None:
    cli("note", "new", "old note")

    r = cli("note", "list", "--json", "--since", "2099-01-01")
    assert r.exit_code == 0
    assert json.loads(r.out) == []


def test_type_daily_selects_exactly_the_daily_notes(cli) -> None:
    cli("note", "today")
    cli("note", "new", "an idea", "--type", "idea")

    r = cli("note", "list", "--json", "--type", "daily")
    records = json.loads(r.out)

    assert len(records) == 1
    assert records[0]["type"] == "daily"


@pytest.mark.parametrize("noun", ["meeting", "note"])
def test_empty_workspace_lists_empty_array_and_exits_0(cli, noun: str) -> None:
    r = cli(noun, "list", "--json")
    assert r.exit_code == 0
    assert json.loads(r.out) == []


@pytest.mark.parametrize("noun", ["meeting", "note"])
def test_empty_workspace_no_json_prints_nothing_and_exits_0(cli, noun: str) -> None:
    r = cli(noun, "list")
    assert r.exit_code == 0
    assert r.out == ""


def test_bad_since_is_usage_error_and_lists_nothing(cli) -> None:
    cli("meeting", "new", "Q3 planning")

    r = cli("meeting", "list", "--json", "--since", "yesterday")
    assert r.exit_code == 2
    assert r.out == ""
    assert "--since" in r.err
