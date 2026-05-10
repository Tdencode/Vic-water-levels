// Shape of a row from water_levels.latest_readings (the view defined in
// supabase/migrations/20260510000000_create_water_levels_schema.sql).
export type LatestReading = {
  company_slug: string;
  company_name: string;
  storage_slug: string;
  storage_name: string;
  source_url: string | null;
  reading_date: string; // ISO date (YYYY-MM-DD)
  volume_ml: number | null;
  capacity_ml: number | null;
  percent_full: number | null;
  scraped_at: string; // ISO timestamp
};

export type CompanyGroup = {
  slug: string;
  name: string;
  totalVolumeMl: number;
  totalCapacityMl: number;
  percentFull: number | null;
  storages: LatestReading[];
};
