"""Tests for level 3 claims verification helpers."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from ref_validator.models.citation import Reference
from ref_validator.models.verification import ExistenceResult
from ref_validator.verification.claims import (
    _fuzzy_match_filename,
    _find_user_pdf,
    _validate_content,
    _looks_like_paper,
)


class TestFuzzyMatchFilename:
    def test_exact_doi_match(self):
        assert _fuzzy_match_filename("10.1038_s41586-020-0001-1.pdf", "", "10.1038/s41586-020-0001-1")

    def test_doi_with_underscore(self):
        assert _fuzzy_match_filename("10.1038_s41586-020-0001-1.pdf", "", "10.1038/s41586-020-0001-1")

    def test_doi_with_dash(self):
        assert _fuzzy_match_filename("10.1038-s41586-020-0001-1.pdf", "", "10.1038/s41586-020-0001-1")

    def test_title_fuzzy_match(self):
        assert _fuzzy_match_filename("attention is all you need.pdf", "Attention Is All You Need", "")

    def test_title_no_match(self):
        assert not _fuzzy_match_filename("completely_different.pdf", "Attention Is All You Need", "")

    def test_empty_inputs(self):
        assert not _fuzzy_match_filename("some_file.pdf", "", "")


class TestFindUserPdf:
    def test_empty_refs_dir(self):
        ref = Reference(ref_id="1", raw_text="test", title="Test Paper")
        assert _find_user_pdf("", ref) is None

    def test_nonexistent_dir(self):
        ref = Reference(ref_id="1", raw_text="test", title="Test Paper")
        assert _find_user_pdf("/nonexistent/path", ref) is None

    def test_finds_matching_pdf(self, tmp_path):
        # Create a PDF file with a matching title name
        pdf_file = tmp_path / "attention is all you need.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        ref = Reference(ref_id="1", raw_text="test", title="Attention Is All You Need")
        result = _find_user_pdf(str(tmp_path), ref)
        assert result is not None
        assert result.name == "attention is all you need.pdf"

    def test_finds_doi_matching_pdf(self, tmp_path):
        pdf_file = tmp_path / "10.1038_s41586-020-0001-1.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        ref = Reference(ref_id="1", raw_text="test", title="Some Title", doi="10.1038/s41586-020-0001-1")
        result = _find_user_pdf(str(tmp_path), ref)
        assert result is not None

    def test_no_match_in_dir(self, tmp_path):
        pdf_file = tmp_path / "unrelated_paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        ref = Reference(ref_id="1", raw_text="test", title="Attention Is All You Need")
        result = _find_user_pdf(str(tmp_path), ref)
        assert result is None


class TestValidateContent:
    """Test post-fetch content validation."""

    def _make_ref(self, title="Random forests", authors=None, doi=""):
        return Reference(
            ref_id="1", raw_text="test", title=title,
            authors=authors or ["Leo Breiman"], doi=doi,
        )

    def _make_existence(self, title="Random forests"):
        return ExistenceResult(found=True, matched_title=title, matched_doi="10.1023/A:1010933404324")

    def test_title_and_author_in_text_passes(self):
        ref = self._make_ref()
        existence = self._make_existence()
        text = "Random forests. Breiman, L. Abstract: Random forests are an ensemble method..."
        assert _validate_content(text, ref, existence) is True

    def test_long_title_alone_passes(self):
        ref = self._make_ref(
            title="Mortality risk attributable to high and low ambient temperature",
            authors=["Antonio Gasparrini"],
        )
        existence = self._make_existence(title="Mortality risk attributable to high and low ambient temperature")
        text = "This study on mortality risk attributable to high and low ambient temperature analyzed data from 384 locations..."
        assert _validate_content(text, ref, existence) is True

    def test_author_in_text_passes(self):
        ref = self._make_ref(title="Some obscure title that wont match")
        existence = self._make_existence(title="Some obscure title that wont match")
        text = "This paper by Breiman introduces a novel approach to classification..."
        assert _validate_content(text, ref, existence) is True

    def test_wrong_paper_fails(self):
        ref = self._make_ref(title="Quantile regression forests", authors=["Nicolai Meinshausen"])
        existence = self._make_existence(title="Quantile regression forests")
        # Text from a DIFFERENT paper
        text = "Censored Quantile Regression Forests by Li and Bradic. We propose a new method for survival analysis..."
        assert _validate_content(text, ref, existence) is False

    def test_landing_page_fails(self):
        ref = self._make_ref()
        existence = self._make_existence()
        text = "Sign in to access this article. Purchase options available. Cookie policy..."
        assert _validate_content(text, ref, existence) is False

    def test_empty_text_fails(self):
        ref = self._make_ref()
        existence = self._make_existence()
        assert _validate_content("", ref, existence) is False

    def test_partial_title_match(self):
        ref = self._make_ref(title="Mortality risk attributable to high and low ambient temperature")
        existence = self._make_existence(title="Mortality risk attributable to high and low ambient temperature")
        text = "In this study on mortality risk attributable to high and low ambient temperature, we analyzed 74 million deaths..."
        assert _validate_content(text, ref, existence) is True

    def test_comma_format_author(self):
        """Author in 'Last, First' format should still match."""
        ref = self._make_ref(title="No match title xyz", authors=["Breiman, Leo"])
        existence = self._make_existence(title="No match title xyz")
        text = "The work of Breiman on random forests has been widely influential..."
        assert _validate_content(text, ref, existence) is True


class TestLooksLikePaper:
    """Test content quality check."""

    def test_short_text_rejected(self):
        assert _looks_like_paper("Short text.") is False

    def test_cookie_page_rejected(self):
        text = "Accept cookies. Cookie policy. " + "Some filler text. " * 200
        assert _looks_like_paper(text) is False

    def test_real_paper_content_accepted(self):
        # Simulate actual paper content with many sentences
        text = "Abstract. This paper presents a novel method. " * 100
        assert _looks_like_paper(text) is True

    def test_link_listing_rejected(self):
        # A page that's just a list of links with no real sentences
        text = "Document 1\nDocument 2\n" * 200
        assert _looks_like_paper(text) is False
