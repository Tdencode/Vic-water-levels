"""Orchestrates all adapters: fetch readings, write to Supabase, log run status."""

from __future__ import annotations

import sys

import click
import structlog

from scrapers.adapters import ALL_ADAPTERS
from scrapers.storage import get_client, persist_company_readings

log = structlog.get_logger()


@click.command()
@click.option("--company", "company", default=None, help="Slug of a single company to run.")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print readings without writing to Supabase (no SUPABASE_* env required).",
)
def main(company: str | None, dry_run: bool) -> int:
    adapters = ALL_ADAPTERS
    if company:
        adapters = [a for a in adapters if a.company_slug == company]
        if not adapters:
            click.echo(f"No adapter found for company slug: {company}", err=True)
            return 1

    if not adapters:
        click.echo("No adapters registered yet.", err=True)
        return 0

    client = None if dry_run else get_client()
    exit_code = 0

    for adapter_cls in adapters:
        adapter = adapter_cls()
        try:
            readings = adapter.fetch()
        except Exception as exc:
            log.error("adapter_failed", company=adapter.company_slug, error=str(exc))
            click.echo(f"{adapter.company_slug}: FAILED — {exc}", err=True)
            exit_code = 1
            continue

        click.echo(f"{adapter.company_slug}: {len(readings)} readings")
        if dry_run:
            for r in readings:
                pct = f"{r.percent_full:>5.1f}%" if r.percent_full is not None else "   n/a"
                vol = f"{r.volume_ml:>11,.0f}" if r.volume_ml is not None else "        n/a"
                click.echo(f"  {pct}  vol={vol} ML  {r.storage_name}")
            continue

        result = persist_company_readings(
            client,
            company_slug=adapter.company_slug,
            company_name=adapter.company_name,
            website_url=adapter.source_url,
            readings=readings,
        )
        summary = (
            f"  wrote {result.rows_inserted} reading rows for {adapter.company_slug}"
        )
        if result.rows_failed:
            summary += f" ({result.rows_failed} failed — see logs)"
            exit_code = 1
        click.echo(summary)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
