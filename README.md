# Vic Water Levels

Daily-scraped water storage levels for Victorian water corporations, stored in Supabase and visualised on a Vercel-hosted Next.js site.

## Architecture

```
┌─────────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  GitHub Actions     │ --> │  Supabase    │ <-- │  Next.js (Vercel)│
│  daily cron         │     │  Postgres    │     │  charts + tables │
│  Python scrapers    │     │  + RLS       │     │                  │
└─────────────────────┘     └──────────────┘     └──────────────────┘
```

- **Scrapers** — Python package in `scrapers/`. One adapter per water company implementing a common `BaseAdapter` interface, run by `scrapers/runner.py`.
- **Schedule** — `.github/workflows/scrape-daily.yml` triggers `runner.py` on a daily cron.
- **Database** — Supabase (Postgres). Schema in `supabase/migrations/`.
- **Web app** — Next.js App Router in `web/`, deployed to Vercel. Reads from Supabase via the public anon key (RLS read-only).

## Repo layout

```
scrapers/                   Python scraper package
  adapters/                 One module per company
  base.py                   BaseAdapter, Reading dataclass
  runner.py                 Orchestrates all adapters
  pyproject.toml
.github/workflows/
  scrape-daily.yml          Cron job
  scrape-manual.yml         workflow_dispatch for testing
supabase/
  migrations/               SQL migrations
web/                        Next.js app (added in a later phase)
sites.md                    Audit notes — per-company data source details
```

## Status

Pre-Phase-1: repo is scaffolded; `sites.md` is being populated by auditing each of the 7 target water company sites.

## Target water companies

The 7 Victorian storage managers we scrape (see `sites.md` for the audit and the rationale for choosing storage managers over retailers):

1. Melbourne Water
2. Goulburn-Murray Water (G-MW) — also covers North East Water region
3. Barwon Water
4. GWMWater (Grampians Wimmera Mallee Water)
5. Coliban Water
6. Southern Rural Water (SRW)
7. Central Highlands Water

## Local development

Scrapers:

```bash
cd scrapers
uv sync                     # or: python -m venv .venv && pip install -e .
uv run python -m scrapers.runner --company melbourne_water --dry-run
```

Web app: see `web/README.md` (added in a later phase).

## Environment variables

| Name                          | Where        | Purpose                                  |
| ----------------------------- | ------------ | ---------------------------------------- |
| `SUPABASE_URL`                | scrapers, web | Supabase project URL                     |
| `SUPABASE_SERVICE_ROLE_KEY`   | scrapers     | Write access for scrapers (GH secret)    |
| `NEXT_PUBLIC_SUPABASE_URL`    | web          | Public URL for the browser client        |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | web        | Anon key, RLS-protected reads only       |
