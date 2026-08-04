"""Unit tests for PDF outline extraction and heading reconstruction."""
import pytest

from materials.formats.pdf_outline import (
    normalize,
    loose,
    build_page_map,
)


class TestNormalize:
    def test_unifies_smart_quotes(self):
        assert normalize("Can’t Do") == normalize("Can't Do")

    def test_unifies_dashes(self):
        assert normalize("What I Left Out — and Why") == \
               normalize("What I Left Out - and Why")

    def test_unescapes_entities(self):
        # The Chapter 12 failure: Docling wrote &amp; where the outline has &.
        assert normalize("Tenure &amp; Promotion") == normalize("Tenure & Promotion")

    def test_case_and_punctuation_insensitive(self):
        assert normalize("A. Practitioner, Not Scholar") == "a practitioner not scholar"

    def test_collapses_whitespace(self):
        assert normalize("A.   Returning  to First") == "a returning to first"


class TestLoose:
    def test_strips_leading_letter_enumerator(self):
        assert loose("a) Strengths") == "strengths"

    def test_strips_leading_number_enumerator(self):
        assert loose("2. Institutional IT Support") == "institutional it support"

    def test_strips_trailing_footnote_marker(self):
        assert loose("1. ChatGPT CustomGPTs 19") == "chatgpt customgpts"

    def test_preserves_chapter_prefix(self):
        # 'CHAPTER 12' must not be stripped to 'genai policies...' — the
        # chapter number is identifying information, not an enumerator.
        assert loose("CHAPTER 12: GenAI Policies").startswith("chapter 12")

    def test_preserves_appendix_prefix(self):
        assert loose("APPENDIX I: Working CustomGPTs").startswith("appendix i")


class TestBuildPageMap:
    def test_maps_lines_to_current_page(self):
        lines = ["<!-- Page 5 -->", "", "body text", "<!-- Page 6 -->", "more"]
        assert build_page_map(lines) == [5, 5, 5, 6, 6]

    def test_lines_before_first_marker_are_zero(self):
        lines = ["preamble", "<!-- Page 1 -->", "body"]
        assert build_page_map(lines) == [0, 1, 1]

    def test_no_markers_at_all(self):
        assert build_page_map(["a", "b"]) == [0, 0]


from materials.formats.pdf_outline import locate_entries


def _lines(*rows):
    return list(rows)


class TestLocateEntries:
    def test_matches_headings_in_order(self):
        lines = _lines(
            "<!-- Page 1 -->", "## Alpha", "body",
            "<!-- Page 2 -->", "## Beta", "body",
        )
        toc = [(1, "Alpha", 1), (1, "Beta", 2)]
        assert locate_entries(toc, lines, build_page_map(lines)) == [1, 4]

    def test_matches_plain_text_not_just_headings(self):
        # Docling renders chapter titles as body text, not '##'.
        lines = _lines("<!-- Page 1 -->", "CHAPTER 1: Beginnings", "body")
        toc = [(1, "CHAPTER 1: Beginnings", 1)]
        assert locate_entries(toc, lines, build_page_map(lines)) == [1]

    def test_ignores_printed_toc_via_page_window(self):
        # 'Alpha' appears in the book's printed TOC on page 2 and for real on
        # page 40. The outline says page 40, so only that one may match.
        lines = _lines(
            "<!-- Page 2 -->", "| Alpha......... | 40 |",
            "<!-- Page 40 -->", "## Alpha", "body",
        )
        toc = [(1, "Alpha", 40)]
        assert locate_entries(toc, lines, build_page_map(lines)) == [3]

    def test_unmatched_entry_is_none(self):
        lines = _lines("<!-- Page 1 -->", "## Alpha")
        toc = [(1, "Alpha", 1), (2, "Missing Heading", 1)]
        assert locate_entries(toc, lines, build_page_map(lines)) == [1, None]

    def test_results_are_strictly_increasing(self):
        lines = _lines(
            "<!-- Page 1 -->", "## Alpha", "## Beta", "## Alpha",
        )
        toc = [(1, "Alpha", 1), (1, "Beta", 1)]
        got = [i for i in locate_entries(toc, lines, build_page_map(lines)) if i is not None]
        assert got == sorted(got)

    def test_entity_escaped_heading_matches(self):
        lines = _lines("<!-- Page 1 -->", "## Tenure &amp; Promotion")
        toc = [(1, "Tenure & Promotion", 1)]
        assert locate_entries(toc, lines, build_page_map(lines)) == [1]

    def test_recovery_pass_finds_entry_after_cursor_overshoot(self):
        # Docling emitted the chapter heading AFTER its own first section.
        # Strict matching locks 'Intro' out; the bounded recovery pass finds it.
        lines = _lines(
            "<!-- Page 5 -->",
            "## A. Intro",          # line 1 - really belongs to Chapter 16
            "body",
            "## CHAPTER 16: End",   # line 3 - emitted late by Docling
            "more",
        )
        toc = [(1, "CHAPTER 16: End", 5), (2, "A. Intro", 5)]
        got = locate_entries(toc, lines, build_page_map(lines))
        assert got[0] == 3          # chapter matched strictly
        assert got[1] is None       # 'A. Intro' precedes it; order forbids a match

    def test_recovery_matches_when_span_allows(self):
        lines = _lines(
            "<!-- Page 5 -->", "## CHAPTER 16: End", "## Strengths Research", "tail",
        )
        # 'a) Strengths' only matches after enumerator-stripping (loose pass).
        toc = [(1, "CHAPTER 16: End", 5), (2, "a) Strengths", 5)]
        got = locate_entries(toc, lines, build_page_map(lines))
        assert got == [1, 2]

    def test_rejects_body_prose_that_extends_a_heading(self):
        # 'The Promise of AI' starts with the heading text and is only a few
        # characters longer, so a length-based tail check would false-match it.
        # Only a dot-leader/page-number tail may match.
        lines = _lines(
            "<!-- Page 5 -->",
            "The Promise of AI",       # body prose - must NOT match
            "## The Promise",          # the real heading - must match
        )
        toc = [(1, "The Promise", 5)]
        assert locate_entries(toc, lines, build_page_map(lines)) == [2]

    def test_still_matches_dot_leader_contents_line(self):
        lines = _lines("<!-- Page 5 -->", "Alpha.......... 40")
        toc = [(1, "Alpha", 5)]
        assert locate_entries(toc, lines, build_page_map(lines)) == [1]


from materials.formats.pdf_outline import apply_heading_levels


class TestApplyHeadingLevels:
    def test_noop_without_outline(self, tmp_path, monkeypatch):
        import materials.formats.pdf_outline as mod
        monkeypatch.setattr(mod, "extract_outline", lambda p: [])
        text = "## Flat\n\nbody\n"
        out, stats = apply_heading_levels(text, "irrelevant.pdf")
        assert out == text
        assert stats["outline_entries"] == 0

    def test_assigns_levels_from_outline(self, monkeypatch):
        import materials.formats.pdf_outline as mod
        monkeypatch.setattr(mod, "extract_outline", lambda p: [
            (1, "CHAPTER 1: Start", 1),
            (2, "A. First", 1),
            (3, "1. Deeper", 1),
        ])
        text = (
            "<!-- Page 1 -->\n"
            "CHAPTER 1: Start\n"
            "## A. First\n"
            "## 1. Deeper\n"
        )
        out, stats = apply_heading_levels(text, "x.pdf")
        assert "## CHAPTER 1: Start" in out
        assert "### A. First" in out
        assert "#### 1. Deeper" in out
        assert stats["outline_located"] == 3

    def test_demotes_headings_absent_from_outline(self, monkeypatch):
        import materials.formats.pdf_outline as mod
        monkeypatch.setattr(mod, "extract_outline", lambda p: [
            (1, "Glossary", 1),
        ])
        text = "<!-- Page 1 -->\n## Glossary\n## Hallucination\n"
        out, _ = apply_heading_levels(text, "x.pdf")
        # Glossary is outline level 1 -> '##'; a term under it must nest at
        # '###', not compete with chapters at '##'.
        assert "## Glossary" in out
        assert "### Hallucination" in out

    def test_caps_at_six_hashes(self, monkeypatch):
        import materials.formats.pdf_outline as mod
        monkeypatch.setattr(mod, "extract_outline", lambda p: [(5, "Deep", 1)])
        text = "<!-- Page 1 -->\n## Deep\n## Orphan\n"
        out, _ = apply_heading_levels(text, "x.pdf")
        assert "###### Deep" in out
        assert "###### Orphan" in out  # capped, not '########'

    def test_preserves_page_markers_and_body(self, monkeypatch):
        import materials.formats.pdf_outline as mod
        monkeypatch.setattr(mod, "extract_outline", lambda p: [(1, "Alpha", 1)])
        text = "<!-- Page 1 -->\n## Alpha\n\nbody text\n"
        out, _ = apply_heading_levels(text, "x.pdf")
        assert "<!-- Page 1 -->" in out
        assert "body text" in out

    def test_reports_unlocated(self, monkeypatch):
        import materials.formats.pdf_outline as mod
        monkeypatch.setattr(mod, "extract_outline", lambda p: [
            (1, "Alpha", 1), (2, "Nowhere", 1),
        ])
        text = "<!-- Page 1 -->\n## Alpha\n"
        _out, stats = apply_heading_levels(text, "x.pdf")
        assert stats["outline_located"] == 1
        assert stats["outline_unlocated"] == 1
