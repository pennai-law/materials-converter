"""PDF conversion tests — guards against regressions in the byte-identical
output that Stage 1's refactor was specified to preserve.

Pinned-golden pattern: two goldens, each pinned to a different code path.
`tests/fixtures/sample.golden.md` tracks the maintained `convert.py` path,
generated once on Docling 2.65.0 at Stage 1 completion and committed. When
Docling upgrades or a deliberate output change lands, it is regenerated as
a reviewable acceptance — turning a silent identity comparison into an
explicit regression guard. `tests/fixtures/sample.legacy.golden.md` tracks
the frozen legacy snapshot (`tests/fixtures/legacy_pdf_to_markdown.py`) and
is itself frozen: it is never regenerated. A divergence there means the
snapshot was edited, not that the golden is stale — revert the edit instead.

Regenerate the maintained golden with:
    ./venv/bin/python convert.py tests/fixtures/sample.pdf -o tests/fixtures/sample.golden.md
"""
import difflib
import hashlib
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample.pdf"
GOLDEN = REPO_ROOT / "tests" / "fixtures" / "sample.golden.md"
LEGACY_GOLDEN = REPO_ROOT / "tests" / "fixtures" / "sample.legacy.golden.md"


def _isolated_fixture(tmpdir: Path) -> Path:
    """Copy the source fixture into tmpdir so PyMuPDF/Docling's incidental
    writes during reading don't mutate the committed fixture. Preserves the
    original filename so document-title and "Converted from:" lines in the
    output match the pinned golden."""
    dest = tmpdir / FIXTURE.name
    shutil.copy(FIXTURE, dest)
    return dest


def _convert_via_legacy(tmpdir: Path) -> Path:
    """Run the frozen legacy code path against an isolated fixture copy."""
    from tests.fixtures import legacy_pdf_to_markdown as legacy

    fixture = _isolated_fixture(tmpdir)
    out = tmpdir / "legacy.md"
    logger = logging.getLogger("legacy_test")
    logger.addHandler(logging.NullHandler())
    legacy.convert_pdf_to_markdown(
        str(fixture),
        output_path=str(out),
        page_markers=True,
        report=False,
        quiet=True,
        logger=logger,
    )
    return out


def _convert_via_new(tmpdir: Path) -> Path:
    """Run the new convert.py CLI against an isolated fixture copy."""
    fixture = _isolated_fixture(tmpdir)
    out = tmpdir / "new.md"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "convert.py"), str(fixture), "-o", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"convert.py failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return out


def _diff_against_golden(
    produced_path: Path,
    label: str,
    golden_path: Path = GOLDEN,
    remedy: str = None,
) -> None:
    """Assert produced output matches the given golden, with a useful diff on failure.

    `remedy` is the guidance printed on failure. It differs per golden: the
    maintained path's golden is regenerated on a deliberate change, while the
    legacy golden is frozen and must never be regenerated — a divergence there
    means the frozen snapshot itself was edited.
    """
    produced = produced_path.read_bytes()
    golden = golden_path.read_bytes()
    if produced == golden:
        return
    if remedy is None:
        remedy = (
            "If this is intentional (Docling upgrade or deliberate behavior "
            "change), regenerate with:\n"
            "  ./venv/bin/python convert.py tests/fixtures/sample.pdf "
            f"-o tests/fixtures/{golden_path.name}"
        )
    produced_lines = produced.decode("utf-8", errors="replace").splitlines()
    golden_lines = golden.decode("utf-8", errors="replace").splitlines()
    diff = "\n".join(difflib.unified_diff(
        golden_lines, produced_lines,
        fromfile=golden_path.name, tofile=label, lineterm="", n=2,
    ))
    pytest.fail(
        f"{label} diverged from {golden_path.name}.\n{remedy}\n\n"
        f"Diff (first 60 lines):\n{diff[:6000]}"
    )


def test_new_matches_golden(tmp_path):
    """convert.py must produce output byte-equal to the pinned golden file.
    This is the primary regression guard for the Stage 1 refactor: any change
    in PDF→markdown output (whether from a Docling upgrade, a refactor, or a
    bug) trips this test and forces an explicit review of whether to accept
    the new output by regenerating the golden."""
    produced = _convert_via_new(tmp_path)
    _diff_against_golden(produced, "convert.py")


def test_legacy_matches_golden(tmp_path):
    """The frozen legacy snapshot must match ITS OWN pinned golden.

    The snapshot is frozen forever, so it gets a frozen reference. This
    catches accidental edits to `tests/fixtures/legacy_pdf_to_markdown.py`.
    It deliberately no longer shares a golden with the maintained path:
    that path now applies markdown cleanup and outline-based heading levels,
    which the snapshot does not and never will."""
    produced = _convert_via_legacy(tmp_path)
    _diff_against_golden(
        produced, "legacy snapshot", LEGACY_GOLDEN,
        remedy=(
            "DO NOT regenerate this golden. The legacy snapshot is frozen, so "
            "this test can only fail if tests/fixtures/legacy_pdf_to_markdown.py "
            "was edited — revert that edit instead. Regenerating this file from "
            "convert.py would overwrite the frozen reference with the maintained "
            "path's output and destroy what this test guards."
        ),
    )


def test_fixture_unchanged_after_conversion(tmp_path):
    """Regression guard: the source fixture must not mutate during a
    conversion. Catches the Stage 1 flake where PyMuPDF wrote back to
    incremental-save PDFs during read paths."""
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    _convert_via_new(tmp_path)
    after = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert before == after, "Source fixture was mutated during a conversion"
