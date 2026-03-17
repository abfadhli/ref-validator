"""Main validation pipeline orchestrator."""

import asyncio
import logging
from pathlib import Path

from ref_validator.apis.arxiv import ArxivAPI
from ref_validator.apis.crossref import CrossRefAPI
from ref_validator.apis.doi_resolver import DOIResolver
from ref_validator.apis.google_scholar import GoogleScholarAPI
from ref_validator.apis.openalex import OpenAlexAPI
from ref_validator.apis.semantic_scholar import SemanticScholarAPI
from ref_validator.apis.unpaywall import UnpaywallAPI
from ref_validator.config import Settings
from ref_validator.extraction.citations import extract_citations
from ref_validator.extraction.pdf import extract_text
from ref_validator.llm.client import LLMClient
from ref_validator.models.citation import ParsedPaper, Reference
from ref_validator.models.cost import CostSummary
from ref_validator.models.report import ValidationReport
from ref_validator.models.verification import (
    CitationVerification,
    VerificationLevel,
    VerificationStatus,
)
from ref_validator.progress import NullProgress, ProgressCallback
from ref_validator.verification.claims import verify_claim
from ref_validator.verification.existence import check_existence
from ref_validator.verification.metadata import check_metadata

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """Orchestrates the full reference validation process."""

    def __init__(self, settings: Settings, track_costs: bool = False):
        self._settings = settings
        self._cost_summary = CostSummary() if track_costs else None
        self._llm = LLMClient(api_key=settings.anthropic_api_key, cost_summary=self._cost_summary)

        # Only create API clients for enabled sources
        self._crossref: CrossRefAPI | None = None
        self._semantic_scholar: SemanticScholarAPI | None = None
        self._openalex: OpenAlexAPI | None = None
        self._google_scholar: GoogleScholarAPI | None = None
        self._unpaywall: UnpaywallAPI | None = None
        self._arxiv: ArxivAPI | None = None
        self._doi_resolver: DOIResolver | None = None

        if settings.use_crossref:
            self._crossref = CrossRefAPI(mailto=settings.unpaywall_email, timeout=settings.api_timeout, max_retries=settings.api_retries)
        if settings.use_semantic_scholar:
            self._semantic_scholar = SemanticScholarAPI(api_key=settings.semantic_scholar_api_key, timeout=settings.api_timeout, max_retries=settings.api_retries)
        if settings.use_openalex:
            self._openalex = OpenAlexAPI(mailto=settings.unpaywall_email, timeout=settings.api_timeout, max_retries=settings.api_retries)
        if settings.use_google_scholar:
            self._google_scholar = GoogleScholarAPI()
        if settings.unpaywall_email:
            self._unpaywall = UnpaywallAPI(email=settings.unpaywall_email, timeout=settings.api_timeout, max_retries=settings.api_retries)
        if settings.use_arxiv:
            self._arxiv = ArxivAPI(timeout=settings.api_timeout)
        # DOI resolver is always available (no API key needed)
        self._doi_resolver = DOIResolver(timeout=settings.api_timeout)

        self._semaphore = asyncio.Semaphore(settings.concurrency)

    async def validate(
        self,
        pdf_path: Path,
        level: VerificationLevel = VerificationLevel.METADATA,
        progress: ProgressCallback | None = None,
    ) -> ValidationReport:
        """Run the full validation pipeline."""
        if progress is None:
            progress = NullProgress()

        # Step 1: Extract text
        progress.on_message("Extracting text from PDF...")
        full_text = await extract_text(pdf_path)

        # Step 2: Extract citations via LLM
        progress.on_message("Extracting citations with LLM...")
        parsed = await extract_citations(
            full_text, self._llm, self._settings.extraction_model
        )

        # Step 3: Verify each reference
        progress.on_start(len(parsed.references), "Verifying references")
        tasks = [
            self._verify_one(ref, parsed, level, progress)
            for ref in parsed.references
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verification_results: list[CitationVerification] = []
        for ref, result in zip(parsed.references, results):
            if isinstance(result, Exception):
                logger.error("Verification failed for ref %s: %s", ref.ref_id, result)
                verification_results.append(
                    CitationVerification(
                        ref_id=ref.ref_id,
                        reference=ref,
                        status=VerificationStatus.ERROR,
                        issues=[str(result)],
                    )
                )
            else:
                verification_results.append(result)

        progress.on_finish()

        return ValidationReport(
            paper_path=str(pdf_path),
            verification_level=level,
            total_references=len(parsed.references),
            results=verification_results,
            cost_summary=self._cost_summary,
        )

    async def _verify_one(
        self,
        reference: Reference,
        parsed: ParsedPaper,
        level: VerificationLevel,
        progress: ProgressCallback,
    ) -> CitationVerification:
        """Verify a single reference with concurrency limiting."""
        async with self._semaphore:
            issues: list[str] = []

            # Level 1: Existence
            existence = await check_existence(
                reference,
                crossref=self._crossref,
                semantic_scholar=self._semantic_scholar,
                openalex=self._openalex,
                google_scholar=self._google_scholar,
                threshold=self._settings.fuzzy_title_threshold,
            )

            if not existence.found:
                progress.on_advance()
                return CitationVerification(
                    ref_id=reference.ref_id,
                    reference=reference,
                    status=VerificationStatus.UNVERIFIED,
                    level_completed=VerificationLevel.EXISTENCE,
                    existence=existence,
                    issues=existence.issues,
                )

            if level == VerificationLevel.EXISTENCE:
                progress.on_advance()
                return CitationVerification(
                    ref_id=reference.ref_id,
                    reference=reference,
                    status=VerificationStatus.VERIFIED,
                    level_completed=VerificationLevel.EXISTENCE,
                    existence=existence,
                )

            # Level 2: Metadata
            metadata = await check_metadata(
                reference, existence,
                crossref=self._crossref,
                semantic_scholar=self._semantic_scholar,
            )
            issues.extend(metadata.issues)

            metadata_ok = metadata.title_match and metadata.year_match
            if level == VerificationLevel.METADATA:
                status = VerificationStatus.VERIFIED if metadata_ok else VerificationStatus.UNVERIFIED
                progress.on_advance()
                return CitationVerification(
                    ref_id=reference.ref_id,
                    reference=reference,
                    status=status,
                    level_completed=VerificationLevel.METADATA,
                    existence=existence,
                    metadata=metadata,
                    issues=issues,
                )

            # Level 3: Claims
            claim_results = []
            citations = parsed.citation_map.get(reference.ref_id, [])
            for cit in citations:
                cr = await verify_claim(
                    cit, existence, reference,
                    llm=self._llm,
                    model=self._settings.verification_model,
                    refs_dir=self._settings.refs_dir,
                    arxiv=self._arxiv,
                    unpaywall=self._unpaywall,
                    doi_resolver=self._doi_resolver,
                    semantic_scholar=self._semantic_scholar,
                    google_scholar=self._google_scholar,
                )
                claim_results.append(cr)

            # Determine overall status
            if not claim_results:
                status = VerificationStatus.VERIFIED if metadata_ok else VerificationStatus.UNVERIFIED
            else:
                any_contradicted = any(cr.supported is False for cr in claim_results)
                if metadata_ok and not any_contradicted:
                    status = VerificationStatus.VERIFIED
                else:
                    status = VerificationStatus.UNVERIFIED

            progress.on_advance()
            return CitationVerification(
                ref_id=reference.ref_id,
                reference=reference,
                status=status,
                level_completed=VerificationLevel.CLAIMS,
                existence=existence,
                metadata=metadata,
                claim_results=claim_results,
                issues=issues,
            )

    async def close(self) -> None:
        """Close all API clients."""
        for client in (
            self._crossref, self._semantic_scholar, self._openalex,
            self._google_scholar, self._unpaywall, self._arxiv, self._doi_resolver,
        ):
            if client is not None:
                await client.close()
