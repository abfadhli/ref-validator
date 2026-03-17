"""Prompt templates for LLM extraction and verification."""

EXTRACTION_SYSTEM = """\
You are an expert academic reference parser. Given the full text of an academic paper, \
extract the reference list and all in-text citations. Be thorough and precise.

For each reference, extract all available metadata fields. For each in-text citation, \
capture the surrounding context (~2 sentences) and what claim the citing paper makes \
about the referenced work."""

REFERENCE_LIST_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref_id": {"type": "string", "description": "Reference identifier (e.g., '1', 'Smith2020')"},
                    "raw_text": {"type": "string", "description": "Full raw text of the reference entry"},
                    "title": {"type": "string"},
                    "authors": {"type": "array", "items": {"type": "string"}},
                    "year": {"type": ["integer", "null"]},
                    "venue": {"type": "string"},
                    "doi": {"type": "string"},
                    "volume": {"type": "string"},
                    "pages": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["ref_id", "raw_text", "title"],
            },
        },
        "in_text_citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref_id": {"type": "string", "description": "Matching reference identifier"},
                    "marker": {"type": "string", "description": "Citation as it appears in text"},
                    "surrounding_text": {"type": "string", "description": "~2 sentences of context"},
                    "claim_made": {"type": "string", "description": "What is claimed about this reference"},
                },
                "required": ["ref_id", "marker", "surrounding_text"],
            },
        },
    },
    "required": ["references", "in_text_citations"],
}

CLAIM_VERIFICATION_SYSTEM = """\
You are an expert at verifying academic claims. Given a claim made in a citing paper \
and the source material (abstract or full text) from the cited paper, determine whether \
the source material supports the claim.

Respond with a structured assessment including whether the claim is supported, your \
confidence level, and a brief explanation."""

CLAIM_VERIFICATION_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {
            "type": ["boolean", "null"],
            "description": "true if supported, false if contradicted, null if inconclusive",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence score 0-1",
        },
        "explanation": {
            "type": "string",
            "description": "Brief explanation of the verdict",
        },
    },
    "required": ["supported", "confidence", "explanation"],
}
