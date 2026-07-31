from __future__ import annotations

import pytest

import endpaper
from endpaper.cli.main import main
from endpaper.tui.status_bar import render_version


def test_tui_and_cli_report_the_same_version(capsys: pytest.CaptureFixture[str]) -> None:
    # main() catches argparse's internal SystemExit (from the `version` action)
    # and converts it to a return code -- see test_exit_codes.py for the same
    # pattern with --help and usage errors.
    assert main(["--version"]) == 0
    cli_output = capsys.readouterr().out.strip()

    assert cli_output == f"endpaper {endpaper.__version__}"
    assert render_version() == f"v{endpaper.__version__}"
