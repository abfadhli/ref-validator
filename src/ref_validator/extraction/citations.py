"""LLM-based citation extraction from paper text."""

from ref_validator.llm.client import LLMClient
from ref_validator.llm.prompts import (
    EXTRACTION_SYSTEM,
    REFERENCE_LIST_TOOL_SCHEMA,
)
from ref_validator.models.citation import InTextCitation, ParsedPaper, Reference


async def extract_citations(
    full_text: str,
    llm: LLMClient,
    model: str,
) -> ParsedPaper:
    """Extract references and in-text citations from paper text using an LLM."""
    # Truncate to ~100k chars to stay within context limits
    truncated = full_text[:100_000]

    result = await llm.extract_structured(
        model=model,
        system=EXTRACTION_SYSTEM,
        user_message=f"Extract all references and in-text citations from this paper:\n\n{truncated}",
        tool_name="extract_citations",
        tool_schema=REFERENCE_LIST_TOOL_SCHEMA,
        max_tokens=16384,
    )

    references = []
    for ref_data in result.get("references", []):
        references.append(
            Reference(
                ref_id=ref_data.get("ref_id", ""),
                raw_text=ref_data.get("raw_text", ""),
                title=ref_data.get("title", ""),
                authors=ref_data.get("authors", []),
                year=ref_data.get("year"),
                venue=ref_data.get("venue", ""),
                doi=ref_data.get("doi", ""),
                volume=ref_data.get("volume", ""),
                pages=ref_data.get("pages", ""),
                url=ref_data.get("url", ""),
            )
        )

    in_text_citations = []
    for cit_data in result.get("in_text_citations", []):
        in_text_citations.append(
            InTextCitation(
                ref_id=cit_data.get("ref_id", ""),
                marker=cit_data.get("marker", ""),
                surrounding_text=cit_data.get("surrounding_text", ""),
                claim_made=cit_data.get("claim_made", ""),
            )
        )

    # Build citation map
    citation_map: dict[str, list[InTextCitation]] = {}
    for cit in in_text_citations:
        citation_map.setdefault(cit.ref_id, []).append(cit)

    return ParsedPaper(
        full_text=full_text,
        references=references,
        in_text_citations=in_text_citations,
        citation_map=citation_map,
    )
