"""Orchestrates all adapters: fetch readings, write to Supabase, log run status.

Stub. Wire-up happens once adapters exist.
"""

from __future__ import annotations

import sys

import click

from scrapers.adapters import ALL_ADAPTERS


@click.command()
@click.option("--company", "company", default=None, help="Slug of a single company to run.")
@click.option("--dry-run", is_flag=True, help="Print readings without writing to Supabase.")
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

    for adapter_cls in adapters:
        adapter = adapter_cls()
        readings = adapter.fetch()
        click.echo(f"{adapter.company_slug}: {len(readings)} readings")
        if dry_run:
            for r in readings:
                click.echo(f"  {r.storage_name}: {r.percent_full}% ({r.volume_ml} ML)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
