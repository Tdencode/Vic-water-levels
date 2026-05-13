-- Fix Supabase security advisory: set latest_readings view to SECURITY INVOKER
-- so RLS policies are evaluated as the querying user, not the view owner.
CREATE OR REPLACE VIEW water_levels.latest_readings
WITH (security_invoker = true)
AS
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
