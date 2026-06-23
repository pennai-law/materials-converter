"""Thin shim — the Rich UX layer now lives in `materials.console`.

Kept at the repo root so the frozen test fixtures (`from console import …`) keep
working. Not part of the installed distribution; runtime code imports
`materials.console` directly.
"""
from materials.console import (  # noqa: F401
    console,
    ConversionProgress,
    conversion_spinner,
    create_conversion_progress,
    create_spinner_progress,
    print_batch_summary,
    print_conversion_report,
    print_error,
    print_header,
    print_step,
    print_success,
    print_warning,
    suppress_docling_logging,
)
