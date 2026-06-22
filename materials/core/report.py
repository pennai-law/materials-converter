"""Shared batch-report writer.

Both the serial (PDF legacy) and parallel batch paths emit the same
`conversion_report.json` schema. Centralizing the writer here keeps the
`--save-report` output identical regardless of which path ran.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def write_conversion_report(reports: List[Dict[str, Any]], target_dir: str) -> str:
    """Write a `conversion_report.json` summarizing a batch run.

    Args:
        reports: per-file report dicts (each with at least `status`, optionally
                 `statistics` with `pages`/`words`).
        target_dir: directory to write `conversion_report.json` into.

    Returns the path written.
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "conversion_report.json"

    successful = sum(1 for r in reports if r.get("status") == "success")
    failed = len(reports) - successful
    total_pages = sum((r.get("statistics") or {}).get("pages", 0) for r in reports)
    total_words = sum((r.get("statistics") or {}).get("words", 0) for r in reports)

    batch_report = {
        "summary": {
            "files_processed": len(reports),
            "successful": successful,
            "failed": failed,
            "total_pages": total_pages,
            "total_words": total_words,
        },
        "files": reports,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(batch_report, f, indent=2)
    return str(report_path)
