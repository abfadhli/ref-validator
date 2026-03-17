"""Citation and reference models."""

from pydantic import BaseModel, Field


class InTextCitation(BaseModel):
    """A citation found in the body text of a paper."""

    ref_id: str = Field(description="Reference identifier (e.g., '1', 'Smith2020')")
    marker: str = Field(description="Citation marker as it appears in text (e.g., '[1]', '(Smith, 2020)')")
    surrounding_text: str = Field(description="~2 sentences of context around the citation")
    claim_made: str = Field(default="", description="What the citing paper claims about this reference")


class Reference(BaseModel):
    """A reference from the bibliography/reference list."""

    ref_id: str = Field(description="Reference identifier matching in-text citations")
    raw_text: str = Field(description="Full raw text of the reference entry")
    title: str = Field(default="")
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None)
    venue: str = Field(default="", description="Journal or conference name")
    doi: str = Field(default="")
    volume: str = Field(default="")
    pages: str = Field(default="")
    url: str = Field(default="")


class ParsedPaper(BaseModel):
    """Result of extracting citations from a paper."""

    full_text: str = Field(description="Full extracted text of the paper")
    references: list[Reference] = Field(default_factory=list)
    in_text_citations: list[InTextCitation] = Field(default_factory=list)
    citation_map: dict[str, list[InTextCitation]] = Field(
        default_factory=dict,
        description="Map from ref_id to all in-text citations of that reference",
    )
