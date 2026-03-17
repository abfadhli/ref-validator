"""Shared test fixtures."""

import pytest

from ref_validator.config import Settings
from ref_validator.models.citation import InTextCitation, ParsedPaper, Reference
from ref_validator.models.verification import ExistenceResult


@pytest.fixture
def settings():
    return Settings(anthropic_api_key="test-key")  # type: ignore[call-arg]


@pytest.fixture
def sample_reference():
    return Reference(
        ref_id="1",
        raw_text="Smith, J. (2020). A great paper. Nature, 580, 100-105.",
        title="A great paper",
        authors=["John Smith"],
        year=2020,
        venue="Nature",
        doi="10.1038/s41586-020-0001-1",
    )


@pytest.fixture
def sample_citation():
    return InTextCitation(
        ref_id="1",
        marker="[1]",
        surrounding_text="Previous work showed that X is true [1]. This has important implications.",
        claim_made="X is true",
    )


@pytest.fixture
def sample_parsed_paper(sample_reference, sample_citation):
    return ParsedPaper(
        full_text="This is a test paper. Previous work showed that X is true [1].\n\nReferences\n1. Smith, J. (2020). A great paper. Nature, 580, 100-105.",
        references=[sample_reference],
        in_text_citations=[sample_citation],
        citation_map={"1": [sample_citation]},
    )


@pytest.fixture
def found_existence():
    return ExistenceResult(
        found=True,
        source_api="crossref",
        matched_doi="10.1038/s41586-020-0001-1",
        matched_title="A great paper",
        title_similarity=1.0,
    )
