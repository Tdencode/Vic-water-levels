import { supabase } from "@/lib/supabase";
import { computeStatewideTotals } from "@/lib/group";
import {
  fillTextClass,
  formatDate,
  formatPercent,
  formatVolume,
} from "@/lib/format";
import StorageTable from "./StorageTable";
import type { LatestReading } from "@/lib/types";

// Re-render at most every hour. The scraper only writes once a day, so
// hourly is plenty fresh and keeps PostgREST quiet.
export const revalidate = 3600;

async function loadReadings(): Promise<LatestReading[]> {
  const { data, error } = await supabase
    .from("latest_readings")
    .select("*")
    .order("company_slug", { ascending: true });
  if (error) throw new Error(`Supabase: ${error.message}`);
  return (data ?? []) as LatestReading[];
}

export default async function HomePage() {
  const readings = await loadReadings();
  const totals = computeStatewideTotals(readings);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Victorian Water Storage Levels
        </h1>
        <p className="mt-3 text-base text-slate-600">
          Daily storage levels for {totals.storageCount} reservoirs across{" "}
          {totals.companyCount} water corporations.{" "}
          {totals.latestReadingDate && (
            <>Last reading {formatDate(totals.latestReadingDate)}.</>
          )}
        </p>
      </header>

      <section
        aria-label="Statewide totals"
        className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3"
      >
        <StatCard
          label="Statewide stored"
          value={formatVolume(totals.totalVolumeMl)}
        />
        <StatCard
          label="Total capacity"
          value={formatVolume(totals.totalCapacityMl)}
        />
        <StatCard
          label="Statewide % full"
          value={formatPercent(totals.percentFull)}
          accentClass={fillTextClass(totals.percentFull)}
        />
      </section>

      <StorageTable readings={readings} />

      <footer className="mt-16 border-t border-slate-200 pt-6 text-sm text-slate-500">
        <p>
          Data scraped daily from the seven Victorian water corporations.
          Volumes shown in megalitres (ML) / gigalitres (GL).
        </p>
      </footer>
    </main>
  );
}

function StatCard({
  label,
  value,
  accentClass,
}: {
  label: string;
  value: string;
  accentClass?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p
        className={`mt-2 text-2xl font-semibold tracking-tight ${
          accentClass ?? "text-slate-900"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
