"use client";

// TODO: persist filters/sort/view via searchParams (skipped in v1).

import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { groupByCompany } from "@/lib/group";
import {
  fillColorClass,
  fillTextClass,
  formatDate,
  formatPercent,
  formatVolume,
} from "@/lib/format";
import { compareNullsLast, sortBy, type SortDir } from "@/lib/sort";
import type { CompanyGroup, LatestReading } from "@/lib/types";

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

export default function StorageTable({ readings }: { readings: LatestReading[] }) {
  const [view, setView] = useState<View>("storages");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [companies, setCompanies] = useState<Set<string>>(new Set());
  const [bucket, setBucket] = useState<Bucket>("all");
  const [storageSortKey, setStorageSortKey] = useState<StorageSortKey>("percent_full");
  const [storageSortDir, setStorageSortDir] = useState<SortDir>("asc");
  const [regionSortKey, setRegionSortKey] = useState<RegionSortKey>("percentFull");
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
      if (companies.size > 0 && !companies.has(r.company_slug)) return false;
      if (!bucketMatch(r.percent_full, bucket)) return false;
      if (q) {
        const hay = `${r.storage_name} ${r.company_name}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [readings, deferredSearch, companies, bucket]);

  const sortedStorages = useMemo(() => {
    return sortBy(
      filteredStorages,
      (r) => r[storageSortKey],
      storageSortDir,
    );
  }, [filteredStorages, storageSortKey, storageSortDir]);

  const regionRows = useMemo<RegionRow[]>(() => {
    const q = deferredSearch.trim().toLowerCase();
    const baseReadings = readings.filter((r) => {
      if (companies.size > 0 && !companies.has(r.company_slug)) return false;
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
  }, [readings, deferredSearch, companies]);

  const sortedRegions = useMemo(() => {
    return [...regionRows].sort((a, b) => {
      const pick = (row: RegionRow) => {
        switch (regionSortKey) {
          case "name": return row.name;
          case "storageCount": return row.storages.length;
          case "totalVolumeMl": return row.totalVolumeMl;
          case "totalCapacityMl": return row.totalCapacityMl;
          case "percentFull": return row.percentFull;
          case "latestReadingDate": return row.latestReadingDate;
        }
      };
      return compareNullsLast(pick(a), pick(b), regionSortDir);
    });
  }, [regionRows, regionSortKey, regionSortDir]);

  function toggleCompany(slug: string) {
    setCompanies((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

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
        selectedCompanies={companies}
        toggleCompany={toggleCompany}
        clearCompanies={() => setCompanies(new Set())}
      />
      <div className="-mx-4 mt-4 overflow-x-auto sm:mx-0">
        {view === "storages" ? (
          <StorageRows
            rows={sortedStorages}
            sortKey={storageSortKey}
            sortDir={storageSortDir}
            onSort={clickStorageHeader}
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
      <p className="mt-3 text-xs text-slate-500">
        {view === "storages"
          ? `${sortedStorages.length} of ${readings.length} storages`
          : `${sortedRegions.length} ${sortedRegions.length === 1 ? "region" : "regions"}`}
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
  selectedCompanies,
  toggleCompany,
  clearCompanies,
}: {
  view: View;
  setView: (v: View) => void;
  search: string;
  setSearch: (s: string) => void;
  bucket: Bucket;
  setBucket: (b: Bucket) => void;
  allCompanies: { slug: string; name: string }[];
  selectedCompanies: Set<string>;
  toggleCompany: (slug: string) => void;
  clearCompanies: () => void;
}) {
  return (
    <div className="sticky top-0 z-20 -mx-4 flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-md sm:border sm:bg-white">
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search storage or region…"
        aria-label="Search"
        className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 placeholder-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
      />
      <CompanyFilter
        allCompanies={allCompanies}
        selected={selectedCompanies}
        toggle={toggleCompany}
        clear={clearCompanies}
      />
      {view === "storages" && (
        <div role="radiogroup" aria-label="Filter by % full" className="flex rounded-md border border-slate-300 bg-white p-0.5 text-xs">
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
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {b.label}
              </button>
            );
          })}
        </div>
      )}
      <div role="radiogroup" aria-label="View" className="ml-auto flex rounded-md border border-slate-300 bg-white p-0.5 text-xs">
        {(["storages", "regions"] as View[]).map((v) => {
          const active = view === v;
          return (
            <button
              key={v}
              role="radio"
              aria-checked={active}
              onClick={() => setView(v)}
              className={`rounded px-2.5 py-1 font-medium capitalize transition ${
                active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {v}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function CompanyFilter({
  allCompanies,
  selected,
  toggle,
  clear,
}: {
  allCompanies: { slug: string; name: string }[];
  selected: Set<string>;
  toggle: (slug: string) => void;
  clear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
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

  const label = selected.size === 0
    ? "All regions"
    : `${selected.size} ${selected.size === 1 ? "region" : "regions"}`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
      >
        {label}
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden className="text-slate-500">
          <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div role="menu" className="absolute left-0 z-30 mt-1 w-64 rounded-md border border-slate-200 bg-white p-1 shadow-lg">
          {allCompanies.map((c) => {
            const checked = selected.has(c.slug);
            return (
              <label
                key={c.slug}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(c.slug)}
                  className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                />
                <span className="flex-1">{c.name}</span>
              </label>
            );
          })}
          {selected.size > 0 && (
            <button
              type="button"
              onClick={clear}
              className="mt-1 w-full rounded px-2 py-1.5 text-left text-xs font-medium text-sky-700 hover:bg-sky-50"
            >
              Clear selection
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
}: {
  label: string;
  sortKey: K;
  active: boolean;
  dir: SortDir;
  onClick: (k: K) => void;
  align?: "left" | "right";
}) {
  const ariaSort = active ? (dir === "asc" ? "ascending" : "descending") : "none";
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      <button
        type="button"
        onClick={() => onClick(sortKey)}
        className={`inline-flex items-center gap-1 transition hover:text-slate-900 ${
          align === "right" ? "flex-row-reverse" : ""
        }`}
      >
        <span>{label}</span>
        <span aria-hidden className={active ? "text-slate-900" : "text-slate-300"}>
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
      <div
        className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-slate-100"
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
      <span className={`tabular-nums ${fillTextClass(pct)}`}>{formatPercent(pct)}</span>
    </div>
  );
}

function StorageRows({
  rows,
  sortKey,
  sortDir,
  onSort,
}: {
  rows: LatestReading[];
  sortKey: StorageSortKey;
  sortDir: SortDir;
  onSort: (k: StorageSortKey) => void;
}) {
  return (
    <table className="w-full text-sm border-separate border-spacing-0">
      <caption className="sr-only">Victorian water storages — sortable</caption>
      <thead className="sticky top-[3.25rem] z-10 bg-slate-50/95 backdrop-blur">
        <tr>
          <SortHeader label="Storage" sortKey="storage_name" active={sortKey === "storage_name"} dir={sortDir} onClick={onSort} />
          <SortHeader label="Region" sortKey="company_name" active={sortKey === "company_name"} dir={sortDir} onClick={onSort} />
          <SortHeader label="% Full" sortKey="percent_full" active={sortKey === "percent_full"} dir={sortDir} onClick={onSort} />
          <SortHeader label="Volume" sortKey="volume_ml" active={sortKey === "volume_ml"} dir={sortDir} onClick={onSort} align="right" />
          <SortHeader label="Capacity" sortKey="capacity_ml" active={sortKey === "capacity_ml"} dir={sortDir} onClick={onSort} align="right" />
          <SortHeader label="Reading" sortKey="reading_date" active={sortKey === "reading_date"} dir={sortDir} onClick={onSort} />
          <th scope="col" className="w-8 px-2 py-2" aria-label="Source"></th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={7} className="px-3 py-6 text-center text-sm text-slate-500">
              No storages match the current filters.
            </td>
          </tr>
        ) : (
          rows.map((r) => (
            <tr key={`${r.company_slug}/${r.storage_slug}`} className="hover:bg-slate-50">
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 font-medium text-slate-900">
                {r.storage_name}
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-600">
                {r.company_name}
              </td>
              <td className="border-b border-slate-100 px-3 py-1.5">
                <PercentCell pct={r.percent_full} />
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700">
                {formatVolume(r.volume_ml)}
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700">
                {formatVolume(r.capacity_ml)}
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-600">
                {formatDate(r.reading_date)}
              </td>
              <td className="border-b border-slate-100 px-2 py-1.5">
                {r.source_url ? (
                  <a
                    href={r.source_url}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Source for ${r.storage_name}`}
                    className="inline-flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
                      <path d="M5 3H3v8h8V9M8 3h3v3M11 3L6.5 7.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
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
      <caption className="sr-only">Victorian water regions — sortable rollup</caption>
      <thead className="sticky top-[3.25rem] z-10 bg-slate-50/95 backdrop-blur">
        <tr>
          <SortHeader label="Region" sortKey="name" active={sortKey === "name"} dir={sortDir} onClick={onSort} />
          <SortHeader label="Storages" sortKey="storageCount" active={sortKey === "storageCount"} dir={sortDir} onClick={onSort} align="right" />
          <SortHeader label="Volume" sortKey="totalVolumeMl" active={sortKey === "totalVolumeMl"} dir={sortDir} onClick={onSort} align="right" />
          <SortHeader label="Capacity" sortKey="totalCapacityMl" active={sortKey === "totalCapacityMl"} dir={sortDir} onClick={onSort} align="right" />
          <SortHeader label="% Full" sortKey="percentFull" active={sortKey === "percentFull"} dir={sortDir} onClick={onSort} />
          <SortHeader label="Latest reading" sortKey="latestReadingDate" active={sortKey === "latestReadingDate"} dir={sortDir} onClick={onSort} />
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={6} className="px-3 py-6 text-center text-sm text-slate-500">
              No regions match the current filters.
            </td>
          </tr>
        ) : (
          rows.map((r) => (
            <tr key={r.slug} className="hover:bg-slate-50">
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 font-medium text-slate-900">
                {r.name}
              </td>
              <td className="border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700">
                {r.storages.length}
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700">
                {formatVolume(r.totalVolumeMl)}
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-700">
                {formatVolume(r.totalCapacityMl)}
              </td>
              <td className="border-b border-slate-100 px-3 py-1.5">
                <PercentCell pct={r.percentFull} />
              </td>
              <td className="whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-600">
                {formatDate(r.latestReadingDate)}
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
