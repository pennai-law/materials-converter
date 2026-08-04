"""Build a small PDF that HAS an outline (bookmark) tree.

The committed `sample.pdf` deliberately has none, so it can't exercise
outline-based heading reconstruction. This builds a 3-page document with a
3-level outline: chapter -> section -> subsection.

Regenerate with:
    "$PY" tests/fixtures/build/build_outline_pdf.py
"""
from pathlib import Path

import fitz
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

OUT = Path(__file__).resolve().parents[1] / "sample_outline.pdf"


def build() -> Path:
    """Build a PDF with a real outline tree."""
    styles = getSampleStyleSheet()
    story = [
        Paragraph("CHAPTER 1: Beginnings", styles["Heading1"]),
        Paragraph("Opening body text for the first chapter.", styles["BodyText"]),
        Paragraph("A. First Section", styles["Heading2"]),
        Paragraph("Body text belonging to the first section.", styles["BodyText"]),
        PageBreak(),
        Paragraph("1. A Subsection", styles["Heading3"]),
        Paragraph("Body text for the subsection, deeper still.", styles["BodyText"]),
        PageBreak(),
        Paragraph("CHAPTER 2: Endings", styles["Heading1"]),
        Paragraph("Body text for the second chapter.", styles["BodyText"]),
    ]
    SimpleDocTemplate(str(OUT), pagesize=letter).build(story)

    # reportlab does not emit bookmarks for plain Paragraphs, so attach the
    # outline explicitly - this is what Acrobat PDFMaker does from Word.
    doc = fitz.open(OUT)
    doc.set_toc([
        [1, "CHAPTER 1: Beginnings", 1],
        [2, "A. First Section", 1],
        [3, "1. A Subsection", 2],
        [1, "CHAPTER 2: Endings", 3],
    ])
    doc.saveIncr()
    doc.close()
    return OUT


if __name__ == "__main__":
    print(f"Wrote {build()}")
