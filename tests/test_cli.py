"""Tests for the CLI."""

from typer.testing import CliRunner

from ref_validator.cli import app

runner = CliRunner()


def test_check_apis_runs():
    """check-apis should run without crashing (APIs may be unreachable in test)."""
    result = runner.invoke(app, ["check-apis"])
    # Should complete without Python exception even if APIs are down
    assert result.exit_code == 0 or "error" in result.output.lower() or "✗" in result.output


def test_validate_missing_file():
    """validate should fail gracefully with missing file."""
    result = runner.invoke(app, ["validate", "nonexistent.pdf"])
    assert result.exit_code != 0
