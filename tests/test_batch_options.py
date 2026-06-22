"""Regression tests for batch-mode option handling and logging setup.

These cover three bugs found in review:
  1. Serial batch (default --workers 1) silently dropped format-specific options.
  2. --save-report wrote no JSON on the parallel path.
  3. --log-file with a missing parent directory crashed before any conversion.

All run without invoking Docling (no model download), so they're cheap.
"""
import json
import logging
from pathlib import Path

from materials.core.base import BaseConverter, ConversionOptions, ConversionResult


class _RecordingConverter(BaseConverter):
    """A converter that records the options each file is converted with."""

    extensions = (".rec",)

    def __init__(self):
        self.seen = []

    def convert(self, input_path, options):
        self.seen.append(options)
        out = options.output_path or str(Path(input_path).with_suffix(".md"))
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text("# stub\n")
        return ConversionResult(status="success", output_file=out, statistics={})


def _make_files(tmp_path, n=2):
    for i in range(n):
        (tmp_path / f"f{i}.rec").write_text("x")


def test_serial_batch_forwards_format_options(tmp_path):
    """Bug 1: serial batch must forward the full ConversionOptions to each file."""
    _make_files(tmp_path)
    conv = _RecordingConverter()
    opts = ConversionOptions(notes_only=True, full=True, ocr=True, page_markers=False)
    out_dir = tmp_path / "out"

    conv.convert_directory(str(tmp_path), output_dir=str(out_dir), workers=1, options=opts)

    assert conv.seen, "converter was never called"
    for seen in conv.seen:
        assert seen.notes_only is True
        assert seen.full is True
        assert seen.ocr is True
        assert seen.page_markers is False
        assert seen.output_path.startswith(str(out_dir))


def test_setup_logging_creates_missing_log_dir(tmp_path):
    """Bug 3: setup_logging must create the log file's parent directory."""
    from materials.core.logging import setup_logging

    log_path = tmp_path / "a" / "b" / "session.log"
    try:
        setup_logging(str(log_path), verbose=False, use_rich=True)
        assert log_path.exists()
    finally:
        logging.getLogger("pdf_converter").handlers = []


def test_write_conversion_report(tmp_path):
    """Bug 2: a shared report writer produces the canonical batch JSON."""
    from materials.core.report import write_conversion_report

    reports = [
        {"input": "a.pdf", "status": "success", "statistics": {"pages": 3}},
        {"input": "b.pdf", "status": "error", "error": "boom"},
    ]
    path = write_conversion_report(reports, str(tmp_path))

    data = json.loads(Path(path).read_text())
    assert data["summary"]["files_processed"] == 2
    assert data["summary"]["successful"] == 1
    assert len(data["files"]) == 2


def test_pdf_batch_with_ocr_delegates_to_options_aware_path(tmp_path, monkeypatch):
    """Bug 1 (PDF path): with ocr/pages set, the serial PDF batch must use the
    options-aware base path, not the legacy batch that ignores those flags."""
    from materials.formats import pdf as pdfmod

    called = {}

    def fake_super(self, input_dir, **kw):
        called.update(kw)
        called["input_dir"] = input_dir
        return {"success_count": 0, "error_count": 0, "reports": []}

    monkeypatch.setattr(BaseConverter, "convert_directory", fake_super)

    conv = pdfmod.PDFConverter()
    opts = ConversionOptions(ocr=True)
    conv.convert_directory(str(tmp_path), workers=1, options=opts)

    assert called.get("options") is opts, "PDF serial batch ignored ocr option"
