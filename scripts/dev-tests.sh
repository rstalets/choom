#!/usr/bin/env bash
set -euo pipefail
# Each worker is mostly idle (see the pytest-xdist comment in pyproject.toml), so
# oversubscribing to ~2x the core count keeps wall time dropping past `-n auto`'s
# 1x -- measured on both a 12-core workstation and CI's 4-vCPU runners.
workers=$(( $(getconf _NPROCESSORS_ONLN) * 2 ))
exec uv run --extra dev pytest -n "$workers" "$@"
