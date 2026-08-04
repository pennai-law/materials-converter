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
# After normalize(), dot leaders collapse to spaces and page numbers to digits.
# Requiring the tail to be digits/whitespace only is what separates a real
# "Heading......... 40" contents line from body prose that merely starts with
# the heading text ("The Promise of AI").
_LEADER_TAIL_RE = re.compile(r"[\d\s]*")


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


def _candidate_text(line: str) -> str:
    """Strip markdown heading hashes so a heading and the same text as a
    plain paragraph compare equal."""
    return _HEADING_PREFIX_RE.sub("", line.strip())


def locate_entries(
    toc: List[OutlineEntry],
    lines: List[str],
    page_of: List[int],
    window: int = 4,
) -> List[Optional[int]]:
    """Find the markdown line index for each outline entry.

    Two constraints keep this honest:
      * page window - a match must sit within `window` pages of the page the
        outline claims, which excludes the book's own printed contents table.
      * monotonic order - matches may only advance, which excludes repeated
        section names like 'a) Strengths' recurring under every platform.
    """
    matches: List[Optional[int]] = []
    cursor = 0

    # Pass 1: strict, monotonic.
    for level, title, page in toc:
        target = normalize(title)
        found = None
        if target:
            for i in range(cursor, len(lines)):
                if abs(page_of[i] - page) > window:
                    continue
                cand = normalize(_candidate_text(lines[i]))
                if not cand:
                    continue
                # Exact, or the line is the heading plus dot-leader/page-number tail.
                if cand == target or (
                    cand.startswith(target)
                    and _LEADER_TAIL_RE.fullmatch(cand[len(target):].strip())
                ):
                    found = i
                    break
        matches.append(found)
        if found is not None:
            cursor = found + 1

    # Pass 2: recovery, bounded by already-matched neighbours so document
    # order is preserved by construction.
    for idx, existing in enumerate(matches):
        if existing is not None:
            continue
        lo = next((matches[j] + 1 for j in range(idx - 1, -1, -1)
                   if matches[j] is not None), 0)
        hi = next((matches[j] for j in range(idx + 1, len(matches))
                   if matches[j] is not None), len(lines))
        if lo >= hi:
            continue
        _level, title, page = toc[idx]
        target = loose(title)
        if len(target) < 5:
            continue
        for i in range(lo, hi):
            if abs(page_of[i] - page) > window:
                continue
            cand = loose(_candidate_text(lines[i]))
            if len(cand) < 5:
                continue
            if cand == target or cand.startswith(target) or target.startswith(cand):
                matches[idx] = i
                break

    return matches
