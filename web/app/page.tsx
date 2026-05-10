import { supabase } from "@/lib/supabase";
import {
  computeStatewideTotals,
  groupByCompany,
} from "@/lib/group";
import {
  fillColorClass,
  fillTextClass,
  formatDate,
  formatPercent,
  formatVolume,
} from "@/lib/format";
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
  const groups = groupByCompany(readings);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Victorian Water Storage Levels
        </h1>
        <p className="mt-3 text-base text-slate-600">
          Daily storage levels for {totals.storageCount} reservoirs across{" "}
          {totals.companyCount} water corporations.{" "}
          {totals.latestReadingDate && (
            <>
              Last reading {formatDate(totals.latestReadingDate)}.
            </>
          )}
        </p>
      </header>

      <section
        aria-label="Statewide totals"
        className="mb-12 grid grid-cols-1 gap-4 sm:grid-cols-3"
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

      <div className="space-y-12">
        {groups.map((group) => (
          <section key={group.slug} aria-labelledby={`company-${group.slug}`}>
            <div className="mb-4 flex items-baseline justify-between border-b border-slate-200 pb-2">
              <h2
                id={`company-${group.slug}`}
                className="text-xl font-semibold text-slate-900"
              >
                {group.name}
              </h2>
              <p className="text-sm text-slate-600">
                <span
                  className={`font-semibold ${fillTextClass(group.percentFull)}`}
                >
                  {formatPercent(group.percentFull)}
                </span>{" "}
                · {formatVolume(group.totalVolumeMl)} of{" "}
                {formatVolume(group.totalCapacityMl)}
              </p>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {group.storages.map((s) => (
                <StorageCard key={s.storage_slug} reading={s} />
              ))}
            </div>
          </section>
        ))}
      </div>

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

function StorageCard({ reading }: { reading: LatestReading }) {
  const pct = reading.percent_full;
  // Cap the bar at 100% even when reservoirs spill above (e.g. SRW data
  // briefly showed 100%+); the badge keeps the true percentage.
  const barWidth = pct == null ? 0 : Math.min(Math.max(pct, 0), 100);

  return (
    <article className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-slate-900">
          {reading.storage_name}
        </h3>
        <span
          className={`shrink-0 text-sm font-semibold ${fillTextClass(pct)}`}
        >
          {formatPercent(pct)}
        </span>
      </div>
      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
      >
        <div
          className={`h-full rounded-full ${fillColorClass(pct)}`}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <p className="mt-3 text-sm text-slate-600">
        {formatVolume(reading.volume_ml)} of {formatVolume(reading.capacity_ml)}
      </p>
      <p className="mt-1 text-xs text-slate-400">
        {formatDate(reading.reading_date)}
      </p>
    </article>
  );
}
