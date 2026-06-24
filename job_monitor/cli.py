from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .collector import collect_and_store
from .config import load_config
from .storage import connect, list_jobs

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def collect(
    config: Path = typer.Option(Path("config/sources.example.yaml"), help="Path to source registry YAML."),
    db: Path = typer.Option(Path("data/jobs.sqlite"), help="SQLite database path."),
    digest: Path = typer.Option(Path("out/digest.md"), help="Markdown digest output path."),
    digest_window_hours: int = typer.Option(24, help="How far back to include jobs in digest."),
) -> None:
    """Collect jobs, store them in SQLite and write a Markdown digest."""

    app_config = load_config(config)
    _, stats = asyncio.run(
        collect_and_store(
            config=app_config,
            db_path=db,
            digest_path=digest,
            digest_window_hours=digest_window_hours,
        )
    )

    console.print("[bold green]Collection completed[/bold green]")
    console.print(f"Sources: {stats.sources_succeeded}/{stats.sources_enabled} succeeded")
    console.print(f"Raw jobs: {stats.raw_seen} · Accepted: {stats.accepted} · Rejected: {stats.rejected}")
    console.print(f"New: {stats.new_jobs} · Updated: {stats.updated_jobs}")
    console.print(f"Digest: {digest}")
    if stats.errors:
        console.print("[bold yellow]Source errors:[/bold yellow]")
        for error in stats.errors:
            console.print(f"- {error}")


@app.command()
def show(
    db: Path = typer.Option(Path("data/jobs.sqlite"), help="SQLite database path."),
    limit: int = typer.Option(20, help="Max rows to display."),
) -> None:
    """Show latest active jobs from SQLite."""

    connection = connect(db)
    jobs = list_jobs(connection, limit=limit)
    connection.close()

    table = Table(title="Latest active frontend jobs")
    table.add_column("Score", justify="right")
    table.add_column("Country")
    table.add_column("Seniority")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Stack")
    table.add_column("URL")

    for job in jobs:
        table.add_row(
            str(job.score),
            job.country,
            job.seniority,
            job.title,
            job.company,
            ", ".join(job.stack[:4]),
            job.canonical_url,
        )

    console.print(table)


@app.command("init-db")
def init_db(db: Path = typer.Option(Path("data/jobs.sqlite"), help="SQLite database path.")) -> None:
    """Create SQLite schema without collecting jobs."""

    connection = connect(db)
    connection.close()
    console.print(f"[bold green]SQLite schema ready:[/bold green] {db}")
