from __future__ import annotations

import tomllib

import pytest

from choom.core.config import get_assistant, set_assistant
from choom.core.errors import UsageError
from choom.core.models import Workspace


def _config_path(workspace: Workspace):
    return workspace.root / ".choom" / "config.toml"


def test_key_created_when_no_assistant_table_exists(tmp_workspace: Workspace) -> None:
    set_assistant(tmp_workspace, "claude")
    text = _config_path(tmp_workspace).read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["assistant"]["name"] == "claude"
    assert data["workspace"]["schema"] == 1


def test_key_inserted_as_first_line_when_table_exists_without_name(
    tmp_workspace: Workspace,
) -> None:
    path = _config_path(tmp_workspace)
    path.write_text(
        path.read_text(encoding="utf-8") + "\n[assistant]\n# a hand-written comment\n",
        encoding="utf-8",
    )
    set_assistant(tmp_workspace, "copilot")
    text = path.read_text(encoding="utf-8")
    assert 'name = "copilot"' in text
    assert "# a hand-written comment" in text
    data = tomllib.loads(text)
    assert data["assistant"]["name"] == "copilot"


def test_existing_name_line_is_replaced_in_place(tmp_workspace: Workspace) -> None:
    path = _config_path(tmp_workspace)
    path.write_text(
        path.read_text(encoding="utf-8") + '\n[assistant]\nname = "claude"\nextra = 1\n',
        encoding="utf-8",
    )
    set_assistant(tmp_workspace, "none")
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["assistant"]["name"] == "none"
    assert data["assistant"]["extra"] == 1


def test_comments_and_unknown_keys_survive(tmp_workspace: Workspace) -> None:
    path = _config_path(tmp_workspace)
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original + '\n# a comment above the table\n[assistant]\nname = "claude"\nnickname = "cc"\n',
        encoding="utf-8",
    )
    set_assistant(tmp_workspace, "copilot")
    text = path.read_text(encoding="utf-8")
    assert "# a comment above the table" in text
    assert 'nickname = "cc"' in text
    assert original in text  # the [workspace] block is untouched


def test_invalid_value_writes_nothing(tmp_workspace: Workspace) -> None:
    path = _config_path(tmp_workspace)
    before = path.read_bytes()
    with pytest.raises(UsageError):
        set_assistant(tmp_workspace, "gpt")
    assert path.read_bytes() == before


def test_workspace_schema_is_untouched(tmp_workspace: Workspace) -> None:
    set_assistant(tmp_workspace, "claude")
    text = _config_path(tmp_workspace).read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["workspace"]["schema"] == 1


def test_get_assistant_missing_file_returns_none(tmp_workspace: Workspace) -> None:
    _config_path(tmp_workspace).unlink()
    assert get_assistant(tmp_workspace) is None


def test_get_assistant_missing_table_returns_none(tmp_workspace: Workspace) -> None:
    assert get_assistant(tmp_workspace) is None


def test_get_assistant_malformed_toml_returns_none(tmp_workspace: Workspace) -> None:
    path = _config_path(tmp_workspace)
    path.write_text("this is not [valid toml", encoding="utf-8")
    assert get_assistant(tmp_workspace) is None


def test_get_assistant_illegal_value_returns_none(tmp_workspace: Workspace) -> None:
    path = _config_path(tmp_workspace)
    path.write_text(
        path.read_text(encoding="utf-8") + '\n[assistant]\nname = "gpt"\n', encoding="utf-8"
    )
    assert get_assistant(tmp_workspace) is None


def test_get_assistant_table_not_a_mapping_returns_none(tmp_workspace: Workspace) -> None:
    path = _config_path(tmp_workspace)
    path.write_text(path.read_text(encoding="utf-8") + "assistant = 1\n", encoding="utf-8")
    assert get_assistant(tmp_workspace) is None


def test_get_assistant_returns_the_configured_value(tmp_workspace: Workspace) -> None:
    set_assistant(tmp_workspace, "copilot")
    assert get_assistant(tmp_workspace) == "copilot"
