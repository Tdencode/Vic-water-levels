-- Vic Water Levels — initial schema
--
-- Stores per-storage daily readings scraped from Victorian water corporation sites.
-- Public read via RLS; writes are service-role only.

create extension if not exists "uuid-ossp";

-- ───────────── Tables ─────────────

create table water_companies (
    id          uuid primary key default uuid_generate_v4(),
    slug        text not null unique,
    name        text not null,
    website_url text,
    created_at  timestamptz not null default now()
);

create table storages (
    id          uuid primary key default uuid_generate_v4(),
    company_id  uuid not null references water_companies(id) on delete cascade,
    slug        text not null,
    name        text not null,
    capacity_ml numeric(14, 2),
    latitude    numeric(9, 6),
    longitude   numeric(9, 6),
    created_at  timestamptz not null default now(),
    unique (company_id, slug)
);

create index storages_company_idx on storages(company_id);

create table readings (
    id            bigserial primary key,
    storage_id    uuid not null references storages(id) on delete cascade,
    reading_date  date not null,
    volume_ml     numeric(14, 2),
    percent_full  numeric(6, 3),
    source_url    text,
    scraped_at    timestamptz not null default now(),
    unique (storage_id, reading_date)
);

create index readings_storage_date_idx on readings(storage_id, reading_date desc);
create index readings_date_idx on readings(reading_date desc);

create table scrape_runs (
    id             bigserial primary key,
    company_id     uuid references water_companies(id) on delete set null,
    started_at     timestamptz not null default now(),
    finished_at    timestamptz,
    status         text not null check (status in ('running', 'success', 'partial', 'failed')),
    rows_inserted  integer not null default 0,
    rows_updated   integer not null default 0,
    error_message  text
);

create index scrape_runs_company_idx on scrape_runs(company_id, started_at desc);

-- ───────────── Row Level Security ─────────────
-- Public anon clients can read everything; only service_role writes.

alter table water_companies enable row level security;
alter table storages         enable row level security;
alter table readings         enable row level security;
alter table scrape_runs      enable row level security;

create policy "public read water_companies" on water_companies for select using (true);
create policy "public read storages"        on storages        for select using (true);
create policy "public read readings"        on readings        for select using (true);
create policy "public read scrape_runs"     on scrape_runs     for select using (true);

-- Writes are restricted to the service role (no policy ⇒ implicit deny for anon/auth).

-- ───────────── Convenience views ─────────────

create or replace view latest_readings as
select distinct on (r.storage_id)
    r.storage_id,
    s.company_id,
    c.slug         as company_slug,
    c.name         as company_name,
    s.slug         as storage_slug,
    s.name         as storage_name,
    s.capacity_ml,
    r.reading_date,
    r.volume_ml,
    r.percent_full,
    r.source_url,
    r.scraped_at
from readings r
join storages s         on s.id = r.storage_id
join water_companies c  on c.id = s.company_id
order by r.storage_id, r.reading_date desc;
