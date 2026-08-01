#!/usr/bin/env bash
set -euo pipefail
exec uv run --extra dev pytest -n auto "$@"
