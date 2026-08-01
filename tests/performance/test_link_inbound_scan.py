from __future__ import annotations

import time
from pathlib import Path

import pytest

from choom.core import links as links_module
from choom.core.links import Link, inbound_links
from choom.core.workspace import init_workspace

_TARGET_ID = "meeting_20260728_a1b2c3d4"

#: ~8.4 KB of filler body per file so 6000 files land around the 50 MB corpus
#: research R2 measured against (candidate-filter scan: 155 ms, budget 500 ms).
_FILLER = (
    "Some ordinary prose about the meeting, discussing budget allocations, "
    "quarterly targets, and follow-up actions for the team. " * 60
)


def _write_document(path: Path, *, doc_id: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: {doc_id}\n"
        'type: "standup"\n'
        'title: "generated"\n'
        "tags: []\n"
        "created: 2026-01-01T09:00:00\n"
        "updated: 2026-01-01T09:00:00\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


@pytest.mark.performance
def test_inbound_links_under_500ms_on_6000_document_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = init_workspace(tmp_path).workspace

    # One real inbound link, buried in the middle of the corpus.
    linking_note = workspace.notes_dir / "2026" / "07" / "linking-note.md"
    _write_document(
        linking_note,
        doc_id="note_20260728_deadbeef",
        body=f"See [Q3 planning](../../../meetings/2026/07/q3.md#{_TARGET_ID}) for context.\n"
        + _FILLER,
    )

    remaining = 5999
    per_month = 250
    month = 1
    year = 2020
    written = 0
    while written < remaining:
        collection_dir = workspace.meetings_dir if written % 2 == 0 else workspace.notes_dir
        prefix = "meeting_" if collection_dir is workspace.meetings_dir else "note_"
        for _ in range(per_month):
            if written >= remaining:
                break
            path = collection_dir / f"{year:04d}" / f"{month:02d}" / f"doc-{written:05d}.md"
            _write_document(path, doc_id=f"{prefix}{year}{month:02d}{written:05d}", body=_FILLER)
            written += 1
        month += 1
        if month > 12:
            month = 1
            year += 1

    corpus_parses = 0
    real_find_links = links_module.find_links

    def _counting_find_links(text: str, *, source: Path) -> tuple[Link, ...]:
        nonlocal corpus_parses
        # tasks.md (empty here, via init_workspace's `.touch()`) is parsed
        # unconditionally once by `_tasks_file_links` -- a constant cost
        # unrelated to the corpus candidate-filter this test protects.
        if source != workspace.tasks_file:
            corpus_parses += 1
        return real_find_links(text, source=source)

    monkeypatch.setattr(links_module, "find_links", _counting_find_links)

    start = time.perf_counter()
    results = inbound_links(workspace, _TARGET_ID)
    elapsed = time.perf_counter() - start

    assert len(results) == 1
    assert results[0].source == linking_note
    # Deterministic form of the same claim the timing budget below protects: the
    # candidate substring filter runs before parsing, so only the one file whose
    # bytes actually contain the id gets parsed -- not all 6000 (see docstring
    # on inbound_links). Immune to CI noise, unlike the timing assertion.
    assert corpus_parses == 1, (
        f"find_links parsed {corpus_parses} corpus files, want 1 (candidate filter skipped)"
    )
    assert elapsed < 0.5, f"inbound_links took {elapsed:.3f}s, budget is 0.5s (SC-006)"
