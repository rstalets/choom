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

    results = inbound_links(workspace, _TARGET_ID)

    assert len(results) == 1
    assert results[0].source == linking_note
    # Deterministic form of the same claim the timing budget below protects: the
    # candidate substring filter runs before parsing, so only the one file whose
    # bytes actually contain the id gets parsed -- not all 6000 (see docstring
    # on inbound_links). Immune to CI noise, unlike the timing assertion, and is
    # the assertion that actually catches the regression this test exists for
    # (see def25fb) -- the elapsed budget below is a secondary backstop.
    assert corpus_parses == 1, (
        f"find_links parsed {corpus_parses} corpus files, want 1 (candidate filter skipped)"
    )

    # Best-of-5, same technique as
    # test_refresh_tick.py::test_refresh_tick_read_stays_inside_one_frame_on_a_representative_month
    # (established in 016656e), applied here preventively (issue #84): this
    # test has the same single-sample, bare-absolute-budget, thousands-of-files
    # shape that flaked on test_scan.py in PR #83, at a comparable corpus size
    # (6000 files here vs. 2000 there). The deterministic corpus_parses
    # assertion above already proves the specific regression this test
    # exists to catch (over-parsing past the candidate filter); this loop
    # times the monkeypatch-free, unaccounted call so the counting wrapper's
    # per-call bookkeeping doesn't inflate the measured cost.
    monkeypatch.undo()
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        inbound_links(workspace, _TARGET_ID)
        samples.append(time.perf_counter() - start)

    assert min(samples) < 0.5, (
        f"inbound_links samples: {[f'{s * 1000:.1f}ms' for s in samples]} (SC-006)"
    )
