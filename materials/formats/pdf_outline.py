"""Reconstruct true heading levels from a PDF's outline (bookmark) tree.

Docling's layout model identifies headings visually — font size, weight,
position — which tells it *that* a line is a heading but not *how deep* it
sits. Every heading therefore comes out as `##`, and chapter titles styled as
display text are sometimes not tagged as headings at all.

A PDF generated from Word via Acrobat PDFMaker carries Word's real heading
styles in its outline tree: exact levels and page numbers, but no body text.
Joining the two recovers the document's true structure.

Not every PDF has an outline (roughly 40% of book-length PDFs in practice),
so every entry point here degrades to a no-op rather than failing.
"""
import html
import logging
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import fitz

OutlineEntry = Tuple[int, str, int]  # (level, title, 1-based page)

_PAGE_MARKER_RE = re.compile(r"^<!--\s*Page\s+(\d+)\s*-->\s*$")
_HEADING_PREFIX_RE = re.compile(r"^#{1,6}\s*")
_TRAILING_FOOTNOTE_RE = re.compile(r"\s+\d+\s*[a-z]?$")
_LEADING_ENUM_RE = re.compile(r"^(?:\d+|[a-z]|[ivxlc]+)\s+")


def extract_outline(pdf_path: str) -> List[OutlineEntry]:
    """Return the PDF's outline as (level, title, page) in document order.

    Returns an empty list when the PDF has no outline — the caller treats
    that as "nothing to do".
    """
    doc = fitz.open(pdf_path)
    try:
        return [(lvl, title, page) for lvl, title, page in doc.get_toc()]
    finally:
        doc.close()


def normalize(s: str) -> str:
    """Fold a heading to a comparable form.

    Handles the three ways the same heading differs between the outline and
    Docling's markdown: HTML entities, smart quotes/dashes, and whitespace.
    """
    s = html.unescape(s)
    s = unicodedata.normalize("NFKD", s)
    for a, b in (("’", "'"), ("‘", "'"), ("”", '"'), ("“", '"')):
        s = s.replace(a, b)
    s = re.sub(r"[‐-―]", "-", s)
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s.lower())
    return " ".join(s.split())


def loose(s: str) -> str:
    """Aggressive fold for the recovery pass.

    Drops leading enumerators ('a)', '2.', 'iv.') and trailing footnote
    markers, which Docling and the outline disagree about. Chapter and
    appendix numbers are preserved — they identify the section rather than
    enumerate it.
    """
    n = normalize(s)
    if n.startswith("chapter ") or n.startswith("appendix "):
        return n
    n = _TRAILING_FOOTNOTE_RE.sub("", n)
    prev = None
    while prev != n:  # nested enumerators, e.g. "1. a) Foo"
        prev = n
        n = _LEADING_ENUM_RE.sub("", n)
    return n.strip()


def build_page_map(lines: List[str]) -> List[int]:
    """Map each markdown line to the page it sits on, via page markers.

    Lines before the first marker map to 0, which never matches a real
    outline page and so is safely excluded from matching.
    """
    page_of: List[int] = []
    current = 0
    for line in lines:
        m = _PAGE_MARKER_RE.match(line)
        if m:
            current = int(m.group(1))
        page_of.append(current)
    return page_of
