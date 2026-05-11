"use client";

// TODO: persist filters/sort/view via searchParams (skipped in v1).

import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
// useRef and useEffect are still used by CompanyFilter for click-outside.
import { groupByCompany } from "@/lib/group";
import {
  fillColorClass,
  fillTextClass,
  formatDate,
  formatPercent,
  formatVolume,
} from "@/lib/format";
import { compareNullsLast, sortBy, type SortDir } from "@/lib/sort";
import { downloadCsv, rowsToCsv, todayIsoDate } from "@/lib/csv";
import { usePersistentStringSet } from "@/lib/persistent-state";
import type { CompanyGroup, LatestReading } from "@/lib/types";

// Versioned localStorage keys — bump if the storage shape ever changes.
const HIDDEN_REGIONS_KEY = "vic-water:hidden-regions:v1";
const HIDDEN_STORAGES_KEY = "vic-water:hidden-storages:v1";

// Canonical per-storage key: matches the React row key already in use.
// Putting the company slug in front keeps it stable even if two companies
// happen to slug a storage name identically (Lal Lal exists in two).
function storageKey(r: {
  company_slug: string;
  storage_slug: string;
}): string {
  return `${r.company_slug}/${r.storage_slug}`;
}

type View = "storages" | "regions";
type Bucket = "all" | "low" | "mid" | "high" | "over";

type StorageSortKey =
  | "storage_name"
  | "company_name"
  | "percent_full"
  | "volume_ml"
  | "capacity_ml"
  | "reading_date";

type RegionRow = CompanyGroup & { latestReadingDate: string | null };

type RegionSortKey =
  | "name"
  | "storageCount"
  | "totalVolumeMl"
  | "totalCapacityMl"
  | "percentFull"
  | "latestReadingDate";

const STORAGE_DEFAULTS: Record<StorageSortKey, SortDir> = {
  storage_name: "asc",
  company_name: "asc",
  percent_full: "asc",
  volume_ml: "desc",
  capacity_ml: "desc",
  reading_date: "desc",
};

const REGION_DEFAULTS: Record<RegionSortKey, SortDir> = {
  name: "asc",
  storageCount: "desc",
  totalVolumeMl: "desc",
  totalCapacityMl: "desc",
  percentFull: "asc",
  latestReadingDate: "desc",
};

const BUCKETS: { value: Bucket; label: string }[] = [
  { value: "all", label: "All" },
  { value: "low", label: "<30%" },
  { value: "mid", label: "30–70%" },
  { value: "high", label: "≥70%" },
  { value: "over", label: "100%+" },
];

function bucketMatch(pct: number | null, bucket: Bucket): boolean {
  if (bucket === "all") return true;
  if (pct == null) return false;
  if (bucket === "low") return pct < 30;
  if (bucket === "mid") return pct >= 30 && pct < 70;
  if (bucket === "high") return pct >= 70 && pct <= 100;
  return pct > 100;
}

export default function StorageTable({
  readings,
}: {
  readings: LatestReading[];
}) {
  const [view, setView] = useState<View>("storages");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  // Persistent across sessions — see usePersistentStringSet for the key.
  const [hiddenCompanies, setHiddenCompanies] =
    usePersistentStringSet(HIDDEN_REGIONS_KEY);
  const [hiddenStorages, setHiddenStorages] =
    usePersistentStringSet(HIDDEN_STORAGES_KEY);
  const [bucket, setBucket] = useState<Bucket>("all");
  const [storageSortKey, setStorageSortKey] =
    useState<StorageSortKey>("percent_full");
  const [storageSortDir, setStorageSortDir] = useState<SortDir>("asc");
  const [regionSortKey, setRegionSortKey] =
    useState<RegionSortKey>("percentFull");
  const [regionSortDir, setRegionSortDir] = useState<SortDir>("asc");

  const allCompanies = useMemo(() => {
    const map = new Map<string, string>();
    for (const r of readings) map.set(r.company_slug, r.company_name);
    return [...map.entries()]
      .map(([slug, name]) => ({ slug, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [readings]);

  const filteredStorages = useMemo(() => {
    const q = deferredSearch.trim().toLowerCase();
    return readings.filter((r) => {
      if (hiddenCompanies.has(r.company_slug)) return false;
      if (hiddenStorages.has(storageKey(r))) return false;
      if (!bucketMatch(r.percent_full, bucket)) return false;
      if (q) {
        const hay = `${r.storage_name} ${r.company_name}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [readings, deferredSearch, hiddenCompanies, hiddenStorages, bucket]);

  const sortedStorages = useMemo(() => {
    return sortBy(filteredStorages, (r) => r[storageSortKey], storageSortDir);
  }, [filteredStorages, storageSortKey, storageSortDir]);

  const regionRows = useMemo<RegionRow[]>(() => {
    const q = deferredSearch.trim().toLowerCase();
    const baseReadings = readings.filter((r) => {
      if (hiddenCompanies.has(r.company_slug)) return false;
      if (hiddenStorages.has(storageKey(r))) return false;
      if (q) {
        const hay = `${r.storage_name} ${r.company_name}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const groups = groupByCompany(baseReadings);
    return groups.map((g) => ({
      ...g,
      latestReadingDate: g.storages.reduce<string | null>(
        (acc, s) => (acc && acc > s.reading_date ? acc : s.reading_date),
        null,
      ),
    }));
  }, [readings, deferredSearch, hiddenCompanies, hiddenStorages]);

  const sortedRegions = useMemo(() => {
    return [...regionRows].sort((a, b) => {
      const pick = (row: RegionRow) => {
        switch (regionSortKey) {
          case "name":
            return row.name;
          case "storageCount":
            return row.storages.length;
          case "totalVolumeMl":
            return row.totalVolumeMl;
          case "totalCapacityMl":
            return row.totalCapacityMl;
          case "percentFull":
            return row.percentFull;
          case "latestReadingDate":
            return row.latestReadingDate;
        }
      };
      return compareNullsLast(pick(a), pick(b), regionSortDir);
    });
  }, [regionRows, regionSortKey, regionSortDir]);

  function toggleCompany(slug: string) {
    setHiddenCompanies((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  function toggleStorage(key: string) {
    setHiddenStorages((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function hideAllVisible() {
    setHiddenStorages((prev) => {
      const next = new Set(prev);
      for (const r of sortedStorages) next.add(storageKey(r));
      return next;
    });
  }

  // Hidden storage rows lookup by key → reading. We need the readable
  // names for the dropdown even when the row itself is filtered out.
  const hiddenStorageReadings = useMemo(() => {
    const byKey = new Map<string, LatestReading>();
    for (const r of readings) byKey.set(storageKey(r), r);
    return [...hiddenStorages]
      .map((k) => byKey.get(k))
      .filter((r): r is LatestReading => r !== undefined)
      .sort((a, b) => a.storage_name.localeCompare(b.storage_name));
  }, [readings, hiddenStorages]);

  function clickStorageHeader(key: StorageSortKey) {
    if (key === storageSortKey) {
      setStorageSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setStorageSortKey(key);
      setStorageSortDir(STORAGE_DEFAULTS[key]);
    }
  }

  function clickRegionHeader(key: RegionSortKey) {
    if (key === regionSortKey) {
      setRegionSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setRegionSortKey(key);
      setRegionSortDir(REGION_DEFAULTS[key]);
    }
  }

  // Export the rows currently visible (filtered + sorted) for whichever
  // view is active. Volumes are written in raw ML so spreadsheets can do
  // their own math; the on-screen GL/TL formatting is presentation only.
  function exportCsv() {
    const date = todayIsoDate();
    if (view === "storages") {
      const headers = [
        "Storage",
        "Region",
        "% Full",
        "Volume (ML)",
        "Capacity (ML)",
        "Reading Date",
        "Source URL",
      ];
      const rows = sortedStorages.map((r) => [
        r.storage_name,
        r.company_name,
        r.percent_full,
        r.volume_ml,
        r.capacity_ml,
        r.reading_date,
        r.source_url ?? "",
      ]);
      downloadCsv(`vic-water-storages-${date}.csv`, rowsToCsv(headers, rows));
    } else {
      const headers = [
        "Region",
        "Storage Count",
        "Total Volume (ML)",
        "Total Capacity (ML)",
        "% Full",
        "Latest Reading",
      ];
      const rows = sortedRegions.map((r) => [
        r.name,
        r.storages.length,
        r.totalVolumeMl,
        r.totalCapacityMl,
        r.percentFull,
        r.latestReadingDate ?? "",
      ]);
      downloadCsv(`vic-water-regions-${date}.csv`, rowsToCsv(headers, rows));
    }
  }

  return (
    <section aria-label="Storage table" className="mb-12">
      <Controls
        view={view}
        setView={setView}
        search={search}
        setSearch={setSearch}
        bucket={bucket}
        setBucket={setBucket}
        allCompanies={allCompanies}
        hiddenCompanies={hiddenCompanies}
        toggleCompany={toggleCompany}
        showAllCompanies={() => setHiddenCompanies(new Set())}
        onExport={exportCsv}
        exportCount={
          view === "storages" ? sortedStorages.length : sortedRegions.length
        }
        hiddenStorageReadings={hiddenStorageReadings}
        onUnhideStorage={toggleStorage}
        onShowAllStorages={() => setHiddenStorages(new Set())}
        onHideAllVisible={hideAllVisible}
        visibleCount={sortedStorages.length}
      />
      <div className="-mx-4 mt-4 overflow-x-auto sm:mx-0">
        {view === "storages" ? (
          <StorageRows
            rows={sortedStorages}
            sortKey={storageSortKey}
            sortDir={storageSortDir}
            onSort={clickStorageHeader}
            onHide={toggleStorage}
          />
        ) : (
          <RegionRows
            rows={sortedRegions}
            sortKey={regionSortKey}
            sortDir={regionSortDir}
            onSort={clickRegionHeader}
          />
        )}
      </div>
      <p className="mt-3 px-1 text-xs text-slate-500 dark:text-slate-400">
        {view === "storages"
          ? `${sortedStorages.length} of ${readings.length} storages`
          : `${sortedRegions.length} ${
              sortedRegions.length === 1 ? "region" : "regions"
            }`}
      </p>
    </section>
  );
}

function Controls({
  view,
  setView,
  search,
  setSearch,
  bucket,
  setBucket,
  allCompanies,
  hiddenCompanies,
  toggleCompany,
  showAllCompanies,
  onExport,
  exportCount,
  hiddenStorageReadings,
  onUnhideStorage,
  onShowAllStorages,
  onHideAllVisible,
  visibleCount,
}: {
  view: View;
  setView: (v: View) => void;
  search: string;
  setSearch: (s: string) => void;
  bucket: Bucket;
  setBucket: (b: Bucket) => void;
  allCompanies: { slug: string; name: string }[];
  hiddenCompanies: Set<string>;
  toggleCompany: (slug: string) => void;
  showAllCompanies: () => void;
  onExport: () => void;
  exportCount: number;
  hiddenStorageReadings: LatestReading[];
  onUnhideStorage: (key: string) => void;
  onShowAllStorages: () => void;
  onHideAllVisible: () => void;
  visibleCount: number;
}) {
  return (
    // Stack on mobile (search on its own row, then the filter chips wrap
    // below) so the controls don't fight for space at 360px wide.
    <div className="sticky top-0 z-20 -mx-4 flex flex-col gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3 sm:mx-0 sm:flex-row sm:flex-wrap sm:items-center sm:rounded-md sm:border sm:bg-white dark:border-slate-800 dark:bg-slate-950 dark:sm:bg-slate-900">
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search storage or region…"
        aria-label="Search"
        className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 placeholder-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-500"
      />
      <div className="flex flex-wrap items-center gap-2">
        <CompanyFilter
          allCompanies={allCompanies}
          hidden={hiddenCompanies}
          toggle={toggleCompany}
          showAll={showAllCompanies}
        />
        <HiddenStoragesMenu
          hiddenReadings={hiddenStorageReadings}
          onUnhide={onUnhideStorage}
          onShowAll={onShowAllStorages}
          onHideAllVisible={onHideAllVisible}
          visibleCount={visibleCount}
          showHideAllVisible={view === "storages"}
        />
        {view === "storages" && (
          <div
            role="radiogroup"
            aria-label="Filter by % full"
            className="flex rounded-md border border-slate-300 bg-white p-0.5 text-xs dark:border-slate-700 dark:bg-slate-800"
          >
            {BUCKETS.map((b) => {
              const active = bucket === b.value;
              return (
                <button
                  key={b.value}
                  role="radio"
                  aria-checked={active}
                  onClick={() => setBucket(b.value)}
                  className={`rounded px-2 py-1 font-medium transition ${
                    active
                      ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  }`}
                >
                  {b.label}
                </button>
              );
            })}
          </div>
        )}
        <div
          role="radiogroup"
          aria-label="View"
          className="ml-auto flex rounded-md border border-slate-300 bg-white p-0.5 text-xs dark:border-slate-700 dark:bg-slate-800"
        >
          {(["storages", "regions"] as View[]).map((v) => {
            const active = view === v;
            return (
              <button
                key={v}
                role="radio"
                aria-checked={active}
                onClick={() => setView(v)}
                className={`rounded px-2.5 py-1 font-medium capitalize transition ${
                  active
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                }`}
              >
                {v}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={onExport}
          disabled={exportCount === 0}
          aria-label={
            view === "storages"
              ? `Download ${exportCount} storages as CSV`
              : `Download ${exportCount} regions as CSV`
          }
          title="Download current view as CSV"
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          <DownloadIcon />
          <span>CSV</span>
        </button>
      </div>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-3.5 w-3.5"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="M7 10l5 5 5-5" />
      <path d="M12 15V3" />
    </svg>
  );
}

function HiddenStoragesMenu({
  hiddenReadings,
  onUnhide,
  onShowAll,
  onHideAllVisible,
  visibleCount,
  showHideAllVisible,
}: {
  hiddenReadings: LatestReading[];
  onUnhide: (key: string) => void;
  onShowAll: () => void;
  onHideAllVisible: () => void;
  visibleCount: number;
  showHideAllVisible: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const hiddenCount = hiddenReadings.length;
  // Hide the menu trigger entirely when there's nothing hidden AND no
  // visible rows to bulk-hide — avoids cluttering the toolbar for users
  // who never use this feature.
  if (hiddenCount === 0 && (!showHideAllVisible || visibleCount === 0)) {
    return null;
  }

  const label =
    hiddenCount === 0 ? "Hide…" : `${hiddenCount} hidden`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        {label}
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          aria-hidden
          className="text-slate-500 dark:text-slate-400"
        >
          <path
            d="M3 4.5l3 3 3-3"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 z-30 mt-1 w-72 rounded-md border border-slate-200 bg-white p-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
        >
          <p className="px-2 pb-1 pt-1 text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Saved in this browser
          </p>
          {showHideAllVisible && visibleCount > 0 && (
            <button
              type="button"
              onClick={() => {
                onHideAllVisible();
                setOpen(false);
              }}
              className="mb-1 w-full rounded px-2 py-1.5 text-left text-xs font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              Hide all {visibleCount} currently visible
            </button>
          )}
          {hiddenCount === 0 ? (
            <p className="px-2 py-2 text-sm text-slate-500 dark:text-slate-400">
              Nothing hidden yet. Use the × on any row to hide a storage.
            </p>
          ) : (
            <>
              <div className="max-h-64 overflow-y-auto">
                {hiddenReadings.map((r) => {
                  const key = storageKey(r);
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => onUnhide(key)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700"
                    >
                      <span className="flex-1 truncate">
                        <span className="font-medium">{r.storage_name}</span>
                        <span className="ml-1.5 text-xs text-slate-500 dark:text-slate-400">
                          {r.company_name}
                        </span>
                      </span>
                      <span className="shrink-0 text-xs text-sky-700 dark:text-sky-400">
                        Unhide
                      </span>
                    </button>
                  );
                })}
              </div>
              <button
                type="button"
                onClick={onShowAll}
                className="mt-1 w-full rounded px-2 py-1.5 text-left text-xs font-medium text-sky-700 hover:bg-sky-50 dark:text-sky-400 dark:hover:bg-sky-950/50"
              >
                Unhide all {hiddenCount}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CompanyFilter({
  allCompanies,
  hidden,
  toggle,
  showAll,
}: {
  allCompanies: { slug: string; name: string }[];
  hidden: Set<string>;
  toggle: (slug: string) => void;
  showAll: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Only count hidden slugs that still exist in the current data — saved
  // hides for companies that have since dropped out shouldn't inflate the
  // count or the "show all" affordance.
  const hiddenCount = allCompanies.filter((c) => hidden.has(c.slug)).length;
  const visibleCount = allCompanies.length - hiddenCount;
  const label =
    hiddenCount === 0
      ? "All sources"
      : `${visibleCount} of ${allCompanies.length} sources`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        {label}
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          aria-hidden
          className="text-slate-500 dark:text-slate-400"
        >
          <path
            d="M3 4.5l3 3 3-3"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 z-30 mt-1 w-64 rounded-md border border-slate-200 bg-white p-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
        >
          <p className="px-2 pb-1 pt-1 text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Saved in this browser
          </p>
          {allCompanies.map((c) => {
            // Checked = visible. Uncheck to hide; persists to localStorage.
            const visible = !hidden.has(c.slug);
            return (
              <label
                key={c.slug}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                <input
                  type="checkbox"
                  checked={visible}
                  onChange={() => toggle(c.slug)}
                  className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-slate-600 dark:bg-slate-900"
                />
                <span className="flex-1">{c.name}</span>
              </label>
            );
          })}
          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={showAll}
              className="mt-1 w-full rounded px-2 py-1.5 text-left text-xs font-medium text-sky-700 hover:bg-sky-50 dark:text-sky-400 dark:hover:bg-sky-950/50"
            >
              Show all sources
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function SortHeader<K extends string>({
  label,
  sortKey,
  active,
  dir,
  onClick,
  align = "left",
  className = "",
}: {
  label: string;
  sortKey: K;
  active: boolean;
  dir: SortDir;
  onClick: (k: K) => void;
  align?: "left" | "right";
  className?: string;
}) {
  const ariaSort = active
    ? dir === "asc"
      ? "ascending"
      : "descending"
    : "none";
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400 ${
        align === "right" ? "text-right" : "text-left"
      } ${className}`}
    >
      <button
        type="button"
        onClick={() => onClick(sortKey)}
        className={`inline-flex items-center gap-1 transition hover:text-slate-900 dark:hover:text-slate-50 ${
          align === "right" ? "flex-row-reverse" : ""
        }`}
      >
        <span>{label}</span>
        <span
          aria-hidden
          className={
            active
              ? "text-slate-900 dark:text-slate-50"
              : "text-slate-300 dark:text-slate-600"
          }
        >
          {active ? (dir === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    </th>
  );
}

function PercentCell({ pct }: { pct: number | null }) {
  const barWidth = pct == null ? 0 : Math.min(Math.max(pct, 0), 100);
  return (
    <div className="flex items-center gap-2">
      {/* Hide the bar at the smallest sizes so the storage name has room;
          the percent number stays visible at all widths. */}
      <div
        className="hidden h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-slate-100 sm:block sm:w-20 dark:bg-slate-800"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ease-out ${fillColorClass(pct)}`}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <span className={`tabular-nums ${fillTextClass(pct)}`}>
        {formatPercent(pct)}
      </span>
    </div>
  );
}

function StorageRows({
  rows,
  sortKey,
  sortDir,
  onSort,
  onHide,
}: {
  rows: LatestReading[];
  sortKey: StorageSortKey;
  sortDir: SortDir;
  onSort: (k: StorageSortKey) => void;
  onHide: (key: string) => void;
}) {
  // Mobile column priority (least-to-most hidden):
  //   always:   Storage, % Full, Volume
  //   sm 640+:  + Capacity
  //   md 768+:  + Region
  //   lg 1024+: + Reading date, Source link
  //
  // Thead is intentionally NOT sticky. The wrapping div uses overflow-x-auto
  // so per CSS spec both axes become scroll containers, which hijacks the
  // sticky context away from the viewport and on some browsers caused the
  // thead to render below the first row of tbody. Sort + filter controls
  // are sticky instead — that's the affordance that actually matters.
  return (
    <table className="w-full text-sm border-separate border-spacing-0">
      <caption className="sr-only">Victorian water storages — sortable</caption>
      <thead className="bg-slate-50 sm:bg-white dark:bg-slate-950 dark:sm:bg-slate-900">
        <tr className="[&>th]:border-b [&>th]:border-slate-200 dark:[&>th]:border-slate-800">
          <SortHeader
            label="Storage"
            sortKey="storage_name"
            active={sortKey === "storage_name"}
            dir={sortDir}
            onClick={onSort}
          />
          <SortHeader
            label="Region"
            sortKey="company_name"
            active={sortKey === "company_name"}
            dir={sortDir}
            onClick={onSort}
            className="hidden md:table-cell"
          />
          <SortHeader
            label="% Full"
            sortKey="percent_full"
            active={sortKey === "percent_full"}
            dir={sortDir}
            onClick={onSort}
          />
          <SortHeader
            label="Volume"
            sortKey="volume_ml"
            active={sortKey === "volume_ml"}
            dir={sortDir}
            onClick={onSort}
            align="right"
          />
          <SortHeader
            label="Capacity"
            sortKey="capacity_ml"
            active={sortKey === "capacity_ml"}
            dir={sortDir}
            onClick={onSort}
            align="right"
            className="hidden sm:table-cell"
          />
          <SortHeader
            label="Reading"
            sortKey="reading_date"
            active={sortKey === "reading_date"}
            dir={sortDir}
            onClick={onSort}
            className="hidden lg:table-cell"
          />
          <th
            scope="col"
            className="hidden w-8 px-2 py-2 lg:table-cell"
            aria-label="Source"
          />
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td
              colSpan={7}
              className="px-3 py-6 text-center text-sm text-slate-500 dark:text-slate-400"
            >
              No storages match the current filters.
            </td>
          </tr>
        ) : (
          rows.map((r) => (
            <tr
              key={storageKey(r)}
              className="group hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <td className="border-b border-slate-100 px-3 py-1.5 font-medium text-slate-900 dark:border-slate-800 dark:text-slate-50">
                <div className="flex min-w-0 items-center gap-1.5">
                  <span className="min-w-0 break-words">{r.storage_name}</span>
                  <button
                    type="button"
                    onClick={() => onHide(storageKey(r))}
                    aria-label={`Hide ${r.storage_name}`}
                    title={`Hide ${r.storage_name}`}
                    className="shrink-0 rounded p-0.5 text-slate-400 opacity-100 transition hover:bg-slate-200 hover:text-slate-700 focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-200"
                  >
                    <CloseIcon />
                  </button>
                </div>
              </td>
              <td className="hidden whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-600 md:table-cell dark:border-slate-800 dark:text-slate-400">
                {r.company_name}
              </td>
              <td className="border-b border-slate-100 px-3 py-1.5 dark:border-slate-800">
                <PercentCell pct={r.percent_full} />
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700 dark:border-slate-800 dark:text-slate-300">
                {formatVolume(r.volume_ml)}
              </td>
              <td className="hidden whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700 sm:table-cell dark:border-slate-800 dark:text-slate-300">
                {formatVolume(r.capacity_ml)}
              </td>
              <td className="hidden whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-600 lg:table-cell dark:border-slate-800 dark:text-slate-400">
                {formatDate(r.reading_date)}
              </td>
              <td className="hidden border-b border-slate-100 px-2 py-1.5 lg:table-cell dark:border-slate-800">
                {r.source_url ? (
                  <a
                    href={r.source_url}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Source for ${r.storage_name}`}
                    className="inline-flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
                      <path
                        d="M5 3H3v8h8V9M8 3h3v3M11 3L6.5 7.5"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </a>
                ) : null}
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}

function RegionRows({
  rows,
  sortKey,
  sortDir,
  onSort,
}: {
  rows: RegionRow[];
  sortKey: RegionSortKey;
  sortDir: SortDir;
  onSort: (k: RegionSortKey) => void;
}) {
  return (
    <table className="w-full text-sm border-separate border-spacing-0">
      <caption className="sr-only">
        Victorian water regions — sortable rollup
      </caption>
      <thead className="bg-slate-50 sm:bg-white dark:bg-slate-950 dark:sm:bg-slate-900">
        <tr className="[&>th]:border-b [&>th]:border-slate-200 dark:[&>th]:border-slate-800">
          <SortHeader
            label="Region"
            sortKey="name"
            active={sortKey === "name"}
            dir={sortDir}
            onClick={onSort}
          />
          <SortHeader
            label="Storages"
            sortKey="storageCount"
            active={sortKey === "storageCount"}
            dir={sortDir}
            onClick={onSort}
            align="right"
          />
          <SortHeader
            label="Volume"
            sortKey="totalVolumeMl"
            active={sortKey === "totalVolumeMl"}
            dir={sortDir}
            onClick={onSort}
            align="right"
          />
          <SortHeader
            label="Capacity"
            sortKey="totalCapacityMl"
            active={sortKey === "totalCapacityMl"}
            dir={sortDir}
            onClick={onSort}
            align="right"
            className="hidden sm:table-cell"
          />
          <SortHeader
            label="% Full"
            sortKey="percentFull"
            active={sortKey === "percentFull"}
            dir={sortDir}
            onClick={onSort}
          />
          <SortHeader
            label="Latest reading"
            sortKey="latestReadingDate"
            active={sortKey === "latestReadingDate"}
            dir={sortDir}
            onClick={onSort}
            className="hidden md:table-cell"
          />
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td
              colSpan={6}
              className="px-3 py-6 text-center text-sm text-slate-500 dark:text-slate-400"
            >
              No regions match the current filters.
            </td>
          </tr>
        ) : (
          rows.map((r) => (
            <tr
              key={r.slug}
              className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <td className="border-b border-slate-100 px-3 py-1.5 font-medium text-slate-900 dark:border-slate-800 dark:text-slate-50">
                <span className="block min-w-0 break-words">{r.name}</span>
              </td>
              <td className="border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700 dark:border-slate-800 dark:text-slate-300">
                {r.storages.length}
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700 dark:border-slate-800 dark:text-slate-300">
                {formatVolume(r.totalVolumeMl)}
              </td>
              <td className="hidden whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700 sm:table-cell dark:border-slate-800 dark:text-slate-300">
                {formatVolume(r.totalCapacityMl)}
              </td>
              <td className="border-b border-slate-100 px-3 py-1.5 dark:border-slate-800">
                <PercentCell pct={r.percentFull} />
              </td>
              <td className="hidden whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-600 md:table-cell dark:border-slate-800 dark:text-slate-400">
                {formatDate(r.latestReadingDate)}
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
