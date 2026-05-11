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
import { ThemeToggle } from "@/components/theme-toggle";

// Always fetch fresh data from Supabase on every request.
export const dynamic = "force-dynamic";

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
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="mb-8 sm:mb-10">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl lg:text-4xl dark:text-slate-50">
              Victorian Water Storage Levels
            </h1>
            <p className="mt-2 text-sm text-slate-600 sm:mt-3 sm:text-base dark:text-slate-400">
              Daily levels for {totals.storageCount} reservoirs across{" "}
              {totals.companyCount} water corporations.
              {totals.latestReadingDate && (
                <> Last reading {formatDate(totals.latestReadingDate)}.</>
              )}
            </p>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <section
        aria-label="Statewide totals"
        className="mb-10 grid grid-cols-1 gap-3 sm:mb-12 sm:grid-cols-3 sm:gap-4"
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

      <footer className="mt-12 border-t border-slate-200 pt-6 text-xs text-slate-500 sm:mt-16 sm:text-sm dark:border-slate-800 dark:text-slate-500">
        <p>
          Data scraped daily from {totals.companyCount} Victorian water
          corporations. Volumes shown in megalitres (ML) / gigalitres (GL) /
          teralitres (TL).
        </p>
        <p className="mt-2">
          Goulburn-Murray Water readings are sourced from the{" "}
          <a
            href="https://waterline.g-mwater.com.au/waterstatus/"
            target="_blank"
            rel="noreferrer"
            className="underline hover:text-slate-700 dark:hover:text-slate-300"
          >
            G-MW Waterline
          </a>{" "}
          status site and are licensed{" "}
          <a
            href="https://creativecommons.org/licenses/by/4.0/"
            target="_blank"
            rel="noreferrer"
            className="underline hover:text-slate-700 dark:hover:text-slate-300"
          >
            CC BY 4.0
          </a>
          .
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
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 sm:text-sm dark:text-slate-400">
        {label}
      </p>
      <p
        className={`mt-1 text-xl font-semibold tracking-tight sm:mt-2 sm:text-2xl ${
          accentClass ?? "text-slate-900 dark:text-slate-50"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
