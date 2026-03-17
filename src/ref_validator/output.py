"""Output formatting: Rich tables and JSON reports."""

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from ref_validator.models.report import ValidationReport
from ref_validator.models.verification import VerificationStatus

STATUS_STYLES = {
    VerificationStatus.VERIFIED: ("VERIFIED", "green"),
    VerificationStatus.UNVERIFIED: ("UNVERIFIED", "red"),
    VerificationStatus.PARTIAL: ("PARTIAL", "yellow"),
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
        f"[yellow]Partial: {report.partial_count}[/yellow]  "
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

    # Cost summary
    if report.cost_summary:
        cs = report.cost_summary
        console.print()
        console.print(f"[dim]Tokens: {cs.total_input_tokens:,} in / {cs.total_output_tokens:,} out[/dim]")
        console.print(f"[dim]Estimated cost: ${cs.total_estimated_cost_usd:.4f}[/dim]")


def report_to_json(report: ValidationReport) -> str:
    """Serialize report to JSON string."""
    return report.model_dump_json(indent=2)


def report_to_dict(report: ValidationReport) -> dict[str, Any]:
    """Serialize report to dict."""
    return report.model_dump(mode="json")
