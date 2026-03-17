"""Output formatting: Rich tables and JSON reports."""

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from ref_validator.models.report import ValidationReport
from ref_validator.models.verification import VerificationLevel, VerificationStatus

STATUS_STYLES = {
    VerificationStatus.VERIFIED: ("VERIFIED", "green"),
    VerificationStatus.UNVERIFIED: ("UNVERIFIED", "red"),
    VerificationStatus.ERROR: ("ERROR", "red bold"),
}


def print_report(report: ValidationReport, console: Console | None = None) -> None:
    """Print a Rich-formatted report to the console."""
    if console is None:
        console = Console()

    console.print()
    console.print(f"[bold]Reference Validation Report[/bold]")
    console.print(f"Paper: {report.paper_path}")
    console.print(f"Level: {report.verification_level.name}")
    console.print(f"References: {report.total_references}")
    console.print()

    # Summary
    console.print(
        f"  [green]Verified: {report.verified_count}[/green]  "
        f"[red]Unverified: {report.unverified_count}[/red]  "
        f"[red bold]Errors: {report.error_count}[/red bold]"
    )
    console.print()

    # Results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Ref", width=6)
    table.add_column("Title", max_width=50)
    table.add_column("Status", width=12)
    table.add_column("Issues", max_width=40)

    for result in report.results:
        label, style = STATUS_STYLES.get(result.status, ("UNKNOWN", "white"))
        title = result.reference.title[:50] if result.reference else "(unknown)"
        issues_text = "; ".join(result.issues[:2]) if result.issues else ""
        table.add_row(
            result.ref_id,
            title,
            f"[{style}]{label}[/{style}]",
            issues_text,
        )

    console.print(table)

    # Claim details for level 3
    if report.verification_level == VerificationLevel.CLAIMS:
        has_claims = any(r.claim_results for r in report.results)
        if has_claims:
            console.print()
            console.print("[bold]Claim Verification Details[/bold]")
            for result in report.results:
                if not result.claim_results:
                    continue
                ref_title = result.reference.title[:40] if result.reference else "(unknown)"
                console.print(f"\n  [bold][{result.ref_id}][/bold] {ref_title}")
                for cr in result.claim_results:
                    if cr.supported is True:
                        icon, style = "supported", "green"
                    elif cr.supported is False:
                        icon, style = "contradicted", "red"
                    else:
                        icon, style = "inconclusive", "yellow"
                    if cr.source_type and cr.source_via:
                        source = f" ({cr.source_type} via {cr.source_via})"
                    elif cr.source_type:
                        source = f" ({cr.source_type})"
                    elif cr.sources_tried:
                        source = f" (no source found, tried: {', '.join(cr.sources_tried)})"
                    else:
                        source = " (no source)"
                    console.print(f"    [{style}]{icon}[/{style}]{source}: {cr.claim[:80]}")
                    if cr.explanation:
                        console.print(f"      [dim]{cr.explanation[:100]}[/dim]")

    # Cost summary
    if report.cost_summary:
        cs = report.cost_summary
        console.print()
        console.print(f"[dim]Tokens: {cs.total_input_tokens:,} in / {cs.total_output_tokens:,} out[/dim]")
        console.print(f"[dim]Estimated cost: ${cs.total_estimated_cost_usd:.4f}[/dim]")


def report_to_markdown(report: ValidationReport) -> str:
    """Serialize report to Markdown string."""
    lines: list[str] = []

    lines.append("# Reference Validation Report")
    lines.append("")
    lines.append(f"- **Paper:** {report.paper_path}")
    lines.append(f"- **Verification level:** {report.verification_level.name} (level {report.verification_level.value})")
    lines.append(f"- **Total references:** {report.total_references}")
    lines.append(f"- **Verified:** {report.verified_count}")
    lines.append(f"- **Unverified:** {report.unverified_count}")
    lines.append(f"- **Errors:** {report.error_count}")
    lines.append("")

    # Results table
    lines.append("## Results")
    lines.append("")
    lines.append("| Ref | Title | Status | Issues |")
    lines.append("|-----|-------|--------|--------|")

    for result in report.results:
        label = result.status.value.upper()
        title = result.reference.title[:50] if result.reference else "(unknown)"
        # Escape pipes in markdown table cells
        title = title.replace("|", "\\|")
        issues_text = "; ".join(result.issues[:2]) if result.issues else ""
        issues_text = issues_text.replace("|", "\\|")
        lines.append(f"| {result.ref_id} | {title} | {label} | {issues_text} |")

    lines.append("")

    # Claim details for level 3
    if report.verification_level == VerificationLevel.CLAIMS:
        has_claims = any(r.claim_results for r in report.results)
        if has_claims:
            lines.append("## Claim Verification Details")
            lines.append("")
            for result in report.results:
                if not result.claim_results:
                    continue
                ref_title = result.reference.title[:60] if result.reference else "(unknown)"
                lines.append(f"### [{result.ref_id}] {ref_title}")
                lines.append("")
                for cr in result.claim_results:
                    if cr.supported is True:
                        verdict = "SUPPORTED"
                    elif cr.supported is False:
                        verdict = "CONTRADICTED"
                    else:
                        verdict = "INCONCLUSIVE"

                    if cr.source_type and cr.source_via:
                        source = f"{cr.source_type} via {cr.source_via}"
                    elif cr.source_type:
                        source = cr.source_type
                    elif cr.sources_tried:
                        source = f"no source found (tried: {', '.join(cr.sources_tried)})"
                    else:
                        source = "no source"

                    lines.append(f"- **{verdict}** ({source}): {cr.claim}")
                    if cr.explanation:
                        lines.append(f"  - {cr.explanation}")
                    if cr.confidence > 0:
                        lines.append(f"  - Confidence: {cr.confidence:.0%}")
                lines.append("")

    # Cost summary
    if report.cost_summary:
        cs = report.cost_summary
        lines.append("## Cost Summary")
        lines.append("")
        lines.append(f"- **Tokens:** {cs.total_input_tokens:,} in / {cs.total_output_tokens:,} out")
        lines.append(f"- **Estimated cost:** ${cs.total_estimated_cost_usd:.4f}")
        lines.append("")

    return "\n".join(lines)


def report_to_json(report: ValidationReport) -> str:
    """Serialize report to JSON string."""
    return report.model_dump_json(indent=2)


def report_to_dict(report: ValidationReport) -> dict[str, Any]:
    """Serialize report to dict."""
    return report.model_dump(mode="json")
