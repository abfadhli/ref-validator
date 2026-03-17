# ref-validator

Validate academic references in PDF papers. Detects fabricated citations by checking whether referenced papers exist, verifying metadata accuracy, and optionally verifying that cited claims are supported by the source material.

## Requirements

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

## Installation

```bash
# Clone and install
git clone https://github.com/abfadhli/ref-validator.git
cd ref-validator
python -m venv venv
source venv/bin/activate   # Linux/macOS
pip install -e .

# With dev dependencies (pytest, ruff, mypy)
pip install -e ".[dev]"
```

## Configuration

ref-validator reads configuration from environment variables or a `.env` file in the working directory.

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key for LLM calls |
| `UNPAYWALL_EMAIL` | No | `""` | Email for Unpaywall and CrossRef polite pool. Enables open-access PDF retrieval and higher rate limits. |
| `SEMANTIC_SCHOLAR_API_KEY` | No | `""` | Semantic Scholar API key for higher rate limits |
| `EXTRACTION_MODEL` | No | `claude-sonnet-4-6` | Model used for citation extraction |
| `VERIFICATION_MODEL` | No | `claude-sonnet-4-6` | Model used for claim verification (level 3) |
| `USE_CROSSREF` | No | `true` | Enable CrossRef API |
| `USE_SEMANTIC_SCHOLAR` | No | `true` | Enable Semantic Scholar API |
| `USE_OPENALEX` | No | `true` | Enable OpenAlex API |
| `USE_GOOGLE_SCHOLAR` | No | `false` | Enable Google Scholar (uses `scholarly`, may be rate-limited) |
| `USE_ARXIV` | No | `true` | Enable arXiv API for free preprint full-text retrieval |
| `REFS_DIR` | No | `""` | Directory containing PDFs of cited papers for level 3 verification |
| `CONCURRENCY` | No | `5` | Default max concurrent API calls |
| `API_TIMEOUT` | No | `30.0` | HTTP timeout in seconds for academic APIs |
| `API_RETRIES` | No | `3` | Number of retry attempts on 429/5xx responses |
| `FUZZY_TITLE_THRESHOLD` | No | `0.85` | Minimum fuzzy-match score (0–1) to consider a title match |

### Setting up `.env`

```bash
cp .env.example .env
# Edit .env and add your API key
```

Minimal `.env`:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Recommended `.env` for best results:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
UNPAYWALL_EMAIL=you@university.edu
SEMANTIC_SCHOLAR_API_KEY=your-key-here
USE_ARXIV=true
```

Providing `UNPAYWALL_EMAIL` enables two things:
1. Access to the CrossRef "polite pool" (faster, more reliable responses).
2. Open-access PDF lookup via Unpaywall, which improves level 3 claim verification.

Setting `USE_ARXIV=true` (default) enables free full-text retrieval of arXiv preprints, significantly improving level 3 claim verification for papers that cite preprints.

## Usage

### Validate references

```bash
# Default: level 2 (existence + metadata)
ref-validator validate paper.pdf

# Level 1: existence check only (fastest, no LLM cost for verification)
ref-validator validate paper.pdf -l 1

# Level 3: full verification including claim checking
ref-validator validate paper.pdf -l 3

# Level 3 with user-supplied PDFs of cited papers (best accuracy)
ref-validator validate paper.pdf -l 3 --refs-dir ./cited_papers/

# Save report as JSON
ref-validator validate paper.pdf -o report.json

# Save report as Markdown
ref-validator validate paper.pdf -o report.md

# Print JSON to stdout
ref-validator validate paper.pdf --json

# Print Markdown to stdout (great for feeding to AI models)
ref-validator validate paper.pdf --md

# Show estimated LLM costs
ref-validator validate paper.pdf --costs

# Increase parallelism for large reference lists
ref-validator validate paper.pdf --concurrency 10

# Combine options
ref-validator validate paper.pdf -l 3 --costs -o report.json --concurrency 10
```

### Check API connectivity

Test that all academic APIs are reachable before running a validation:

```bash
ref-validator check-apis
```

Output:

```
  ✓ CrossRef
  ✓ Semantic Scholar
  ✓ OpenAlex
  ✓ arXiv
```

### CLI reference

```
ref-validator validate [OPTIONS] PAPER

Arguments:
  PAPER    Path to PDF paper [required]

Options:
  -l, --level INTEGER        Verification level 1-3 [default: 2]
  -o, --output PATH          Save report to file (.json or .md)
  --json                     Print JSON to stdout
  --md                       Print Markdown to stdout
  --costs                    Track and display LLM costs
  --concurrency INTEGER      Max concurrent API calls [default: 5]
  --refs-dir PATH            Directory containing PDFs of cited papers
  --help                     Show this message and exit
```

```
ref-validator check-apis

  Test connectivity to all academic APIs.
```

## Verification levels

### Level 1 — Existence

Checks whether each reference actually exists as a published work.

- Looks up by DOI first (fast and authoritative).
- Falls back to title search across CrossRef, Semantic Scholar, and OpenAlex in parallel.
- Uses fuzzy title matching (default threshold: 0.85) to handle minor formatting differences.
- No LLM cost beyond the initial citation extraction step.

**Best for:** Quick sanity checks, large reference lists, cost-sensitive runs.

### Level 2 — Metadata (default)

Everything in level 1, plus metadata comparison.

- Compares title, authors, year, and venue against API data.
- Author matching uses last-name set overlap (≥50%).
- Year matching allows ±1 tolerance (covers pre-print vs. publication date differences).
- Venue matching uses fuzzy comparison (threshold: 0.6) to handle abbreviations.

**Best for:** General-purpose validation. Catches fabricated references that have plausible-sounding but incorrect metadata.

### Level 3 — Claims

Everything in level 2, plus claim verification.

- For each in-text citation, extracts what the citing paper claims about the reference.
- Retrieves source content using a priority chain of full-text sources (see below).
- Uses the LLM to assess whether the source material supports the claim.
- Confidence is reduced by 20% when only an abstract is available (vs. full text).
- Output shows which source was used per claim (e.g., `full_text via arxiv`, `abstract via semantic_scholar`).

**Full-text retrieval priority chain** (stops at first success):

| Priority | Source | Type | Description |
|---|---|---|---|
| 1 | **User-supplied PDF** (`--refs-dir`) | full_text | Best quality — user-curated PDFs matched by title or DOI |
| 2 | **arXiv** | full_text | Free full text for preprints, searched by title |
| 3 | **Unpaywall** | full_text | Open-access PDFs via DOI lookup |
| 4 | **DOI direct resolution** | full_text | Follows DOI links to grab HTML/PDF from publisher pages (MDPI, PLOS, Frontiers, etc.) |
| 5 | **Semantic Scholar** | abstract | Abstract fallback via DOI |
| 6 | **Google Scholar** | abstract | Last resort abstract via title search |

**Best for:** Thorough validation of critical papers. Higher LLM cost due to per-claim verification calls.

#### Supplying your own PDFs

For paywalled papers where automated retrieval fails, you can supply PDFs directly:

```bash
mkdir cited_papers/
# Add PDFs named by title or DOI:
#   cited_papers/attention is all you need.pdf
#   cited_papers/10.1038_s41586-020-0001-1.pdf
ref-validator validate paper.pdf -l 3 --refs-dir ./cited_papers/
```

Matching rules:
- **By DOI:** filename contains the DOI (with `/` replaced by `_` or `-`).
- **By title:** filename fuzzy-matches the reference title (threshold: 0.6).
- User-supplied PDFs are always checked first and take priority over all API sources.

You can also set the `REFS_DIR` environment variable instead of using `--refs-dir` each time.

## Understanding the output

### Console output

The Rich-formatted table shows one row per reference:

| Column | Description |
|---|---|
| **Ref** | Reference identifier from the paper (e.g., `1`, `Smith2020`) |
| **Title** | Extracted title (truncated to 50 chars) |
| **Status** | `VERIFIED`, `UNVERIFIED`, or `ERROR` |
| **Issues** | What went wrong, if anything |

Status meanings:

- **VERIFIED** — All checks passed at the requested level.
- **UNVERIFIED** — Paper not found, metadata doesn't match, or a claim was contradicted.
- **ERROR** — Something went wrong (API failure, timeout, etc.). The issue is noted but the run continues.

At level 3, a **Claim Verification Details** section follows the table:

```
Claim Verification Details

  [1] Attention Is All You Need
    supported (full_text via arxiv): Transformer models outperform RNNs on translation tasks
      Source confirms BLEU score improvements on WMT benchmarks
    inconclusive (no source found, tried: refs_dir, arxiv, unpaywall, doi_resolver): Model scales linearly
```

Each claim shows its verdict (`supported`, `contradicted`, or `inconclusive`) and which source provided the content. When no source was found, the list of attempted sources is shown.

### Markdown report

The Markdown output (via `--md` or `-o report.md`) is readable by both humans and AI models:

```bash
# Print to stdout
ref-validator validate paper.pdf -l 3 --md

# Save to file
ref-validator validate paper.pdf -l 3 -o report.md

# Feed directly to an AI model
ref-validator validate paper.pdf -l 3 --md | claude "Analyze this report"
```

The `-o` flag auto-detects format from the file extension: `.md` saves Markdown, anything else saves JSON.

### JSON report

The JSON output (via `--json` or `-o report.json`) contains the full structured report:

```json
{
  "paper_path": "paper.pdf",
  "timestamp": "2026-03-17T12:00:00",
  "verification_level": 2,
  "total_references": 25,
  "results": [
    {
      "ref_id": "1",
      "status": "verified",
      "existence": {
        "found": true,
        "source_api": "crossref",
        "matched_doi": "10.1234/example",
        "title_similarity": 0.97
      },
      "metadata": {
        "title_match": true,
        "authors_match": true,
        "year_match": true,
        "venue_match": true
      },
      "issues": []
    }
  ],
  "cost_summary": null
}
```

At level 3, each result includes a `claim_results` array:

```json
{
  "claim_results": [
    {
      "claim": "Transformer models outperform RNNs on translation tasks",
      "supported": true,
      "confidence": 0.92,
      "explanation": "Source confirms BLEU score improvements...",
      "source_type": "full_text",
      "source_via": "arxiv",
      "sources_tried": ["refs_dir", "arxiv"]
    }
  ]
}
```

## Using as a library

ref-validator can be used as a Python library for integration into other tools:

```python
import asyncio
from pathlib import Path

from ref_validator.config import Settings
from ref_validator.models.verification import VerificationLevel
from ref_validator.pipeline import ValidationPipeline

async def main():
    settings = Settings()
    pipeline = ValidationPipeline(settings, track_costs=True)

    try:
        report = await pipeline.validate(
            Path("paper.pdf"),
            level=VerificationLevel.METADATA,
        )

        for result in report.results:
            print(f"[{result.ref_id}] {result.status.value}: {result.reference.title}")

        if report.cost_summary:
            print(f"Cost: ${report.cost_summary.total_estimated_cost_usd:.4f}")
    finally:
        await pipeline.close()

asyncio.run(main())
```

### Custom progress callback

Implement the `ProgressCallback` protocol to receive progress updates:

```python
from ref_validator.progress import ProgressCallback

class MyProgress:
    def on_start(self, total: int, description: str) -> None:
        print(f"Starting: {description} ({total} items)")

    def on_advance(self, amount: int = 1) -> None:
        print(".", end="", flush=True)

    def on_message(self, message: str) -> None:
        print(message)

    def on_finish(self) -> None:
        print("\nDone!")

report = await pipeline.validate(path, level=level, progress=MyProgress())
```

## Cost estimates

LLM costs depend on paper length and number of references. Approximate costs per paper using `claude-sonnet-4-6`:

| Level | Typical cost | Notes |
|---|---|---|
| 1 | $0.01–0.03 | One LLM call for citation extraction only |
| 2 | $0.01–0.03 | Same as level 1 (metadata checks use APIs, not the LLM) |
| 3 | $0.05–0.30 | Additional LLM call per in-text citation for claim verification |

Use `--costs` to see actual token usage and estimated cost after each run.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
coverage run -m pytest && coverage report

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Troubleshooting

**"ANTHROPIC_API_KEY is required"** — Set the `ANTHROPIC_API_KEY` environment variable or add it to `.env`.

**References marked UNVERIFIED that you know exist** — Try lowering the fuzzy match threshold:
```
FUZZY_TITLE_THRESHOLD=0.75
```

**Rate limiting errors** — Reduce concurrency (`--concurrency 2`) or add API keys for higher limits (`SEMANTIC_SCHOLAR_API_KEY`).

**"No text content found in PDF"** — The PDF may be image-based (scanned). ref-validator requires text-based PDFs. Use OCR software first.

**Slow performance** — Increase concurrency (`--concurrency 10`). Add `UNPAYWALL_EMAIL` to access the CrossRef polite pool.

**Level 3 claims all "inconclusive"** — This usually means no full text could be retrieved. Try:
1. Supply PDFs of the cited papers via `--refs-dir ./cited_papers/`.
2. Ensure `USE_ARXIV=true` (default) — this helps for papers citing arXiv preprints.
3. Set `UNPAYWALL_EMAIL` to enable open-access PDF lookup.
4. Some paywalled papers can still be resolved via DOI direct resolution (enabled by default).

**User-supplied PDFs not being matched** — Check that the filename matches the reference title or DOI. The DOI `/` should be replaced with `_` or `-` in the filename (e.g., `10.1038_s41586-020-0001-1.pdf`). Title matching uses fuzzy comparison with a 0.6 threshold.
