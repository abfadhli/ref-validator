"""Tests for the validation pipeline."""

from ref_validator.models.citation import InTextCitation, ParsedPaper, Reference
from ref_validator.models.cost import CostSummary, TokenUsage
from ref_validator.models.report import ValidationReport
from ref_validator.models.verification import (
    CitationVerification,
    VerificationLevel,
    VerificationStatus,
)


def test_validation_report_counts():
    results = [
        CitationVerification(ref_id="1", status=VerificationStatus.VERIFIED),
        CitationVerification(ref_id="2", status=VerificationStatus.VERIFIED),
        CitationVerification(ref_id="3", status=VerificationStatus.UNVERIFIED),
        CitationVerification(ref_id="4", status=VerificationStatus.PARTIAL),
        CitationVerification(ref_id="5", status=VerificationStatus.ERROR),
    ]
    report = ValidationReport(
        paper_path="test.pdf",
        verification_level=VerificationLevel.METADATA,
        total_references=5,
        results=results,
    )
    assert report.verified_count == 2
    assert report.unverified_count == 1
    assert report.partial_count == 1
    assert report.error_count == 1


def test_cost_summary():
    cs = CostSummary()
    cs.add(TokenUsage(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500))
    cs.add(TokenUsage(model="claude-sonnet-4-6", input_tokens=2000, output_tokens=1000))

    assert cs.total_input_tokens == 3000
    assert cs.total_output_tokens == 1500
    assert cs.total_estimated_cost_usd > 0


def test_parsed_paper_model():
    ref = Reference(ref_id="1", raw_text="Test ref", title="Test")
    cit = InTextCitation(ref_id="1", marker="[1]", surrounding_text="context")
    paper = ParsedPaper(
        full_text="text",
        references=[ref],
        in_text_citations=[cit],
        citation_map={"1": [cit]},
    )
    assert len(paper.references) == 1
    assert "1" in paper.citation_map
