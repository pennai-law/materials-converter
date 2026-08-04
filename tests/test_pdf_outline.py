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
