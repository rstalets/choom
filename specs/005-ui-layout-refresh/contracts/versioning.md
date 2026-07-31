# Contract: version resolution and the release dry run

**Feature**: `005-ui-layout-refresh`

Two things are pinned here: what `endpaper` reports as its version in every context it can run in,
and what the dry-run workflow guarantees. Both exist to make FR-042 and FR-043 true about the
artifact rather than about a string someone remembered to edit.

---

## Version resolution

### Source of truth

| Context | `__version__` resolves to | Mechanism |
|---|---|---|
| Built wheel or sdist, installed | The version stamped at build time | `endpaper/_version.py`, written by the hatch-vcs build hook |
| Built from a tagged commit | The tag, e.g. `0.0.4` | hatch-vcs reads the VCS tag |
| Built with `SETUPTOOLS_SCM_PRETEND_VERSION` set | That value | Release dry run |
| Built from a tarball with no VCS metadata | `0.0.0` | `fallback-version` |
| Source checkout, no built package | `0.0.0` | `ImportError` fallback in `__init__.py` |

### Configuration

```toml
# pyproject.toml
[tool.hatch.version]
source = "vcs"
fallback-version = "0.0.0"          # changed from "0.0.1"

[tool.hatch.build.hooks.vcs]
version-file = "src/endpaper/_version.py"
enable-by-default = false           # see "Verification during implementation" below
```

```python
# src/endpaper/__init__.py
try:
    from endpaper._version import __version__
except ImportError:            # source checkout, not a built package
    __version__ = "0.0.0"
```

```gitignore
# .gitignore
src/endpaper/_version.py
```

### Guarantees

1. **The two front-ends never disagree.** `cli/main.py` and the TUI status bar import the same
   attribute. A test asserts the string the status bar renders equals `endpaper --version`'s output,
   with no literal version in the assertion.
2. **`0.0.0` means "not a release."** It is never produced by a tagged build, so a screenshot or bug
   report showing `v0.0.0` identifies itself as development code (FR-043).
3. **No literal version lives in tracked source.** `_version.py` is generated and ignored;
   `__init__.py` carries only the fallback. Nothing needs updating at release time.
4. **No runtime dependency is added.** Resolution is an import that either succeeds or does not —
   no `git`, no network, no `importlib.metadata` lookup (constitution III and the platform
   constraints).

### Verification during implementation

hatch-vcs documents the build hook as running on *build or install*, so `uv pip install -e .` may
write `_version.py` and produce a development version instead of the `0.0.0` fallback. Confirmed:
it does. Scoping the hook to the wheel/sdist *targets* does not exempt an editable install, because
an editable install builds the `wheel` target too — target scoping cannot tell the two apart.

The mechanism that does work is hatchling's own hook gate: `enable-by-default = false` on the hook,
enabled explicitly with the `HATCH_BUILD_HOOKS_ENABLE=1` environment variable wherever a real stamp
is wanted — `publish.yml`'s build step and `release-dry-run.yml`. `uv pip install -e .` never sets
that variable, so the hook stays off and `__init__.py`'s `ImportError` fallback fires. FR-043 is the
acceptance criterion: a source checkout reports `0.0.0`.

---

## Release dry-run workflow

`.github/workflows/release-dry-run.yml`

### Trigger and input

```yaml
on:
  workflow_dispatch:
    inputs:
      version:
        description: "Proposed version, e.g. 0.0.4"
        required: true
        type: string
```

### Steps, in order

| # | Step | Fails the run when |
|---|---|---|
| 1 | Validate `inputs.version` against a PEP 440-shaped pattern | The input is not a plausible version |
| 2 | Checkout with `fetch-depth: 0` | — |
| 3 | `ruff format --check .`, `ruff check .`, `mypy` | The quality gate fails |
| 4 | `uv run --extra dev pytest -q` | Any test fails |
| 5 | `uv build --no-sources` with `SETUPTOOLS_SCM_PRETEND_VERSION: ${{ inputs.version }}` and `HATCH_BUILD_HOOKS_ENABLE: "1"` | The build fails |
| 6 | Install the built wheel into a clean environment | The wheel does not install |
| 7 | Assert `endpaper --version` equals `endpaper ${{ inputs.version }}` | The stamp does not match the request |
| 8 | `actions/upload-artifact` with `dist/*` | — |

### Guarantees

1. **It cannot publish.** The job declares no `environment: pypi` and no `id-token: write`
   permission, so it holds no credential capable of uploading to PyPI. This is structural, not a
   matter of remembering to omit a step.
2. **It changes nothing.** No tag, no commit, no release. `SETUPTOOLS_SCM_PRETEND_VERSION` affects
   one build process and leaves the repository as it found it.
3. **It proves the version stamp.** Step 7 is the check that makes R9's claim testable on a real
   artifact rather than in a unit test.
4. **It is at least as strict as review.** Steps 3–4 run the full constitution gate.

### Relationship to `publish.yml`

`publish.yml` keeps its `release: [published]` trigger and its publish step, unchanged by this
feature. Its test job currently runs `pytest` only, so a release can carry lint or type errors that
would block a pull request; the dry run is deliberately stricter. Aligning `publish.yml` is a
one-line change owned by the release process, not by this feature — see research R9a.
