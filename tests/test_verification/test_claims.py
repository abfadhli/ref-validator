"""Tests for level 3 claims verification helpers."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from ref_validator.models.citation import Reference
from ref_validator.verification.claims import _fuzzy_match_filename, _find_user_pdf


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
