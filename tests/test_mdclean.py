"""Unit tests for markdown post-processing cleanup.

These guard two Docling output defects: HTML entities leaking into markdown
(which breaks downstream text matching) and headings emitted with no text.
"""
import pytest

from materials.core.mdclean import unescape_entities, drop_empty_headings


class TestUnescapeEntities:
    def test_ampersand(self):
        assert unescape_entities("Tenure &amp; Promotion") == "Tenure & Promotion"

    def test_angle_brackets(self):
        assert unescape_entities("a &lt; b &gt; c") == "a < b > c"

    def test_numeric_entity(self):
        assert unescape_entities("it&#39;s") == "it's"

    def test_quote_entity(self):
        assert unescape_entities("&quot;quoted&quot;") == '"quoted"'

    def test_noop_when_clean(self):
        text = "# Heading\n\nPlain text with an & ampersand.\n"
        assert unescape_entities(text) == text

    def test_leaves_page_markers_intact(self):
        text = "<!-- Page 40 -->\n\nTenure &amp; Promotion"
        assert unescape_entities(text) == "<!-- Page 40 -->\n\nTenure & Promotion"

    def test_single_pass_only(self):
        # Double-escaped input unescapes exactly one level, never loops.
        assert unescape_entities("&amp;lt;") == "&lt;"


class TestDropEmptyHeadings:
    def test_removes_empty_heading_and_its_blank_line(self):
        assert drop_empty_headings("a\n\n## \n\nb") == "a\n\nb"

    def test_removes_bare_hashes_without_trailing_space(self):
        assert drop_empty_headings("a\n\n###\n\nb") == "a\n\nb"

    def test_keeps_headings_with_text(self):
        text = "## Real Heading\n\nbody\n"
        assert drop_empty_headings(text) == text

    def test_keeps_hash_inside_body_text(self):
        text = "See item #4 below\n"
        assert drop_empty_headings(text) == text

    def test_multiple_empty_headings(self):
        assert drop_empty_headings("a\n\n## \n\n## \n\nb") == "a\n\nb"
