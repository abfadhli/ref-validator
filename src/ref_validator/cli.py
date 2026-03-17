"""Typer CLI for ref-validator."""

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console

from ref_validator.config import Settings
from ref_validator.errors import RefValidatorError
from ref_validator.models.verification import VerificationLevel
from ref_validator.output import print_report, report_to_json

app = typer.Typer(name="ref-validator", help="Validate academic references in papers.")
console = Console()


class RichProgress:
    """Progress callback using Rich."""

    def __init__(self, console: Console):
        self._console = console
        self._total = 0
        self._done = 0

    def on_start(self, total: int, description: str) -> None:
        self._total = total
        self._done = 0
        self._console.print(f"[bold]{description}[/bold] ({total} items)")

    def on_advance(self, amount: int = 1) -> None:
        self._done += amount
        self._console.print(f"  [{self._done}/{self._total}]", end="\r")

    def on_message(self, message: str) -> None:
        self._console.print(f"[dim]{message}[/dim]")

    def on_finish(self) -> None:
        self._console.print(f"  Done. [{self._done}/{self._total}]")


@app.command()
def validate(
    paper: Path = typer.Argument(..., help="Path to PDF paper", exists=True, readable=True),
    level: int = typer.Option(2, "-l", "--level", min=1, max=3, help="Verification level (1-3)"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Save JSON report to file"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON to stdout"),
    costs: bool = typer.Option(False, "--costs", help="Track and display LLM costs"),
    concurrency: int = typer.Option(5, "--concurrency", min=1, max=50, help="Max concurrent API calls"),
) -> None:
    """Validate references in an academic paper."""
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(1)

    settings.concurrency = concurrency
    verification_level = VerificationLevel(level)

    async def _run() -> None:
        from ref_validator.pipeline import ValidationPipeline

        pipeline = ValidationPipeline(settings, track_costs=costs)
        try:
            progress = RichProgress(console) if not json_output else None
            report = await pipeline.validate(paper, level=verification_level, progress=progress)

            if json_output:
                print(report_to_json(report))
            else:
                print_report(report, console)

            if output:
                output.write_text(report_to_json(report))
                console.print(f"\n[dim]Report saved to {output}[/dim]")

        except RefValidatorError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
        finally:
            await pipeline.close()

    asyncio.run(_run())


@app.command()
def check_apis() -> None:
    """Test connectivity to all academic APIs."""

    async def _run() -> None:
        try:
            settings = Settings()  # type: ignore[call-arg]
        except Exception:
            settings = Settings(anthropic_api_key="dummy")  # type: ignore[call-arg]

        from ref_validator.apis.crossref import CrossRefAPI
        from ref_validator.apis.openalex import OpenAlexAPI
        from ref_validator.apis.semantic_scholar import SemanticScholarAPI

        apis = [
            ("CrossRef", CrossRefAPI(mailto=settings.unpaywall_email)),
            ("Semantic Scholar", SemanticScholarAPI(api_key=settings.semantic_scholar_api_key)),
            ("OpenAlex", OpenAlexAPI(mailto=settings.unpaywall_email)),
        ]

        for name, client in apis:
            try:
                ok = await client.check_connectivity()
                if ok:
                    console.print(f"  [green]✓[/green] {name}")
                else:
                    console.print(f"  [red]✗[/red] {name}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {name}: {e}")
            finally:
                await client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
