-- Victorian water-levels tracker schema.
--
-- Lives in its own `water_levels` schema so it can coexist with other
-- apps in the same Supabase project. After applying, expose the schema
-- in the Supabase dashboard:
--
--     Project Settings -> API -> "Exposed schemas" -> add `water_levels`
--
-- Without that step, PostgREST won't serve any of these tables.

CREATE SCHEMA IF NOT EXISTS water_levels;

-- Stable per-company metadata. The slug is the natural primary key
-- (e.g. 'melbourne-water', 'coliban-water') so foreign keys read clearly.
CREATE TABLE IF NOT EXISTS water_levels.companies (
    slug         TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    website      TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per storage per company. (company_slug, slug) is the natural key
-- but a synthetic id keeps reading FKs compact.
CREATE TABLE IF NOT EXISTS water_levels.storages (
    id            BIGSERIAL PRIMARY KEY,
    company_slug  TEXT NOT NULL
                  REFERENCES water_levels.companies(slug)
                  ON DELETE RESTRICT,
    slug          TEXT NOT NULL,
    name          TEXT NOT NULL,
    source_url    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_slug, slug)
);

CREATE INDEX IF NOT EXISTS storages_company_slug_idx
    ON water_levels.storages (company_slug);

-- One row per (storage, day). capacity_ml is denormalised onto the row
-- because reservoir capacities change over time (dam upgrades, sediment
-- surveys, etc.) and we want each reading self-contained.
CREATE TABLE IF NOT EXISTS water_levels.readings (
    id            BIGSERIAL PRIMARY KEY,
    storage_id    BIGINT NOT NULL
                  REFERENCES water_levels.storages(id)
                  ON DELETE CASCADE,
    reading_date  DATE NOT NULL,
    volume_ml     NUMERIC,
    capacity_ml   NUMERIC,
    percent_full  NUMERIC,
    scraped_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (storage_id, reading_date)
);

CREATE INDEX IF NOT EXISTS readings_reading_date_idx
    ON water_levels.readings (reading_date DESC);

CREATE INDEX IF NOT EXISTS readings_storage_id_date_idx
    ON water_levels.readings (storage_id, reading_date DESC);

-- Atomic upsert RPC the scraper calls once per Reading. Handles the
-- company + storage upserts so the scraper doesn't round-trip three times
-- per reading.
CREATE OR REPLACE FUNCTION water_levels.upsert_reading(
    p_company_slug   TEXT,
    p_company_name   TEXT,
    p_storage_slug   TEXT,
    p_storage_name   TEXT,
    p_source_url     TEXT,
    p_reading_date   DATE,
    p_volume_ml      NUMERIC,
    p_capacity_ml    NUMERIC,
    p_percent_full   NUMERIC
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = water_levels, pg_catalog
AS $$
DECLARE
    v_storage_id BIGINT;
    v_reading_id BIGINT;
BEGIN
    INSERT INTO companies (slug, name)
        VALUES (p_company_slug, p_company_name)
        ON CONFLICT (slug) DO UPDATE
            SET name = EXCLUDED.name,
                updated_at = now();

    INSERT INTO storages (company_slug, slug, name, source_url)
        VALUES (p_company_slug, p_storage_slug, p_storage_name, p_source_url)
        ON CONFLICT (company_slug, slug) DO UPDATE
            SET name = EXCLUDED.name,
                source_url = EXCLUDED.source_url,
                updated_at = now()
        RETURNING id INTO v_storage_id;

    INSERT INTO readings (
        storage_id, reading_date, volume_ml, capacity_ml, percent_full
    )
    VALUES (
        v_storage_id, p_reading_date, p_volume_ml, p_capacity_ml, p_percent_full
    )
    ON CONFLICT (storage_id, reading_date) DO UPDATE
        SET volume_ml    = EXCLUDED.volume_ml,
            capacity_ml  = EXCLUDED.capacity_ml,
            percent_full = EXCLUDED.percent_full,
            scraped_at   = now()
    RETURNING id INTO v_reading_id;

    RETURN v_reading_id;
END;
$$;

-- Convenience view for the public site: latest reading per storage,
-- joined with company metadata.
CREATE OR REPLACE VIEW water_levels.latest_readings AS
SELECT
    c.slug          AS company_slug,
    c.name          AS company_name,
    s.slug          AS storage_slug,
    s.name          AS storage_name,
    s.source_url,
    r.reading_date,
    r.volume_ml,
    r.capacity_ml,
    r.percent_full,
    r.scraped_at
FROM water_levels.storages s
JOIN water_levels.companies c ON c.slug = s.company_slug
JOIN LATERAL (
    SELECT volume_ml, capacity_ml, percent_full, reading_date, scraped_at
    FROM water_levels.readings r2
    WHERE r2.storage_id = s.id
    ORDER BY r2.reading_date DESC
    LIMIT 1
) r ON TRUE;

-- RLS: anonymous users get read-only access; only service_role can write.
-- The RPC is SECURITY DEFINER so it can be granted to a scoped writer role
-- later without touching table-level grants.
ALTER TABLE water_levels.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE water_levels.storages  ENABLE ROW LEVEL SECURITY;
ALTER TABLE water_levels.readings  ENABLE ROW LEVEL SECURITY;

CREATE POLICY companies_public_read ON water_levels.companies
    FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY storages_public_read ON water_levels.storages
    FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY readings_public_read ON water_levels.readings
    FOR SELECT TO anon, authenticated USING (true);

-- Schema + table grants. service_role bypasses RLS in Supabase, so it
-- writes directly; anon/authenticated read through the policies above.
GRANT USAGE ON SCHEMA water_levels TO anon, authenticated, service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA water_levels
    TO anon, authenticated;
GRANT SELECT ON water_levels.latest_readings TO anon, authenticated;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA water_levels
    TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA water_levels
    TO service_role;
GRANT EXECUTE ON FUNCTION water_levels.upsert_reading TO service_role;
