"""The rg command line interface (unrelated to the ripgrep executable)."""

import json
import logging

import typer
from pydantic import ValidationError

from research_graph import __version__
from research_graph.config import get_settings
from research_graph.logging_setup import setup_logging

app = typer.Typer(no_args_is_help=True, help="Anime data engineering research scaffold.")


@app.command()
def version() -> None:
    """Show the installed project version."""
    typer.echo(__version__)


@app.command("check-config")
def check_config() -> None:
    """Validate settings and show a safe configuration summary."""
    try:
        settings = get_settings()
    except ValidationError:
        # ValidationError can include raw input, potentially containing a secret.
        typer.echo("Invalid configuration. Check RG_* variables and .env.", err=True)
        raise typer.Exit(code=2) from None
    setup_logging(settings.log_level, settings.log_format)
    logging.getLogger(__name__).info("Configuration validated")
    # Never serialize Settings directly: it includes github_token.
    summary = {
        "data_dir": str(settings.data_dir),
        "log_level": settings.log_level,
        "log_format": settings.log_format,
        "request_timeout": settings.request_timeout,
        "max_concurrency": settings.max_concurrency,
        "github_token_configured": bool(settings.github_token),
    }
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
