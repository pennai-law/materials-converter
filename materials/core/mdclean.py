"""Markdown cleanup shared across converters.

Docling emits two artifacts that are wrong for markdown output:

1. HTML entities (`&amp;`, `&lt;`, `&gt;`). Markdown is not HTML, and the
   entities break any downstream text matching — `Tenure &amp; Promotion`
   does not match `Tenure & Promotion`.
2. Headings with no text (`## ` alone on a line), produced when the layout
   model tags a decorative or image-only block as a heading.

Both are pure string transforms with no I/O, so they are trivially testable
and safe to apply to any format's output.
"""
import html
import re
from typing import Match

# Restricted to a known entity set rather than a blanket html.unescape() so
# stray ampersands in legal prose ("Smith & Wesson & Co") are never mangled.
_ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|apos|nbsp|#\d+|#[xX][0-9a-fA-F]+);")

# A heading line with nothing but hashes/whitespace, plus one following blank
# line if present — so removal doesn't leave a double blank behind.
_EMPTY_HEADING_RE = re.compile(r"^#{1,6}[ \t]*\n(?:[ \t]*\n)?", re.MULTILINE)


def unescape_entities(md_text: str) -> str:
    """Convert HTML entities emitted by Docling back to literal characters.

    Single-pass by construction: `&amp;lt;` becomes `&lt;`, not `<`.
    """
    def _sub(m: Match) -> str:
        return html.unescape(m.group(0))

    return _ENTITY_RE.sub(_sub, md_text)


def drop_empty_headings(md_text: str) -> str:
    """Remove headings that carry no text."""
    return _EMPTY_HEADING_RE.sub("", md_text)
