import type { CompanyGroup, LatestReading } from "./types";

// Group readings by company and sort: companies by total capacity desc,
// storages within a company by capacity desc. Storages without a known
// capacity sort last so a single missing value doesn't displace the big
// dams that anchor the page.
export function groupByCompany(readings: LatestReading[]): CompanyGroup[] {
  const byCompany = new Map<string, CompanyGroup>();

  for (const r of readings) {
    let group = byCompany.get(r.company_slug);
    if (!group) {
      group = {
        slug: r.company_slug,
        name: r.company_name,
        totalVolumeMl: 0,
        totalCapacityMl: 0,
        percentFull: null,
        storages: [],
      };
      byCompany.set(r.company_slug, group);
    }
    group.storages.push(r);
    group.totalVolumeMl += r.volume_ml ?? 0;
    group.totalCapacityMl += r.capacity_ml ?? 0;
  }

  for (const group of byCompany.values()) {
    group.percentFull =
      group.totalCapacityMl > 0
        ? (group.totalVolumeMl / group.totalCapacityMl) * 100
        : null;
    group.storages.sort((a, b) => (b.capacity_ml ?? 0) - (a.capacity_ml ?? 0));
  }

  return [...byCompany.values()].sort(
    (a, b) => b.totalCapacityMl - a.totalCapacityMl,
  );
}

export type StatewideTotals = {
  storageCount: number;
  companyCount: number;
  totalVolumeMl: number;
  totalCapacityMl: number;
  percentFull: number | null;
  latestReadingDate: string | null;
};

export function computeStatewideTotals(
  readings: LatestReading[],
): StatewideTotals {
  let totalVolumeMl = 0;
  let totalCapacityMl = 0;
  let latestReadingDate: string | null = null;
  const companies = new Set<string>();

  for (const r of readings) {
    totalVolumeMl += r.volume_ml ?? 0;
    totalCapacityMl += r.capacity_ml ?? 0;
    companies.add(r.company_slug);
    if (!latestReadingDate || r.reading_date > latestReadingDate) {
      latestReadingDate = r.reading_date;
    }
  }

  return {
    storageCount: readings.length,
    companyCount: companies.size,
    totalVolumeMl,
    totalCapacityMl,
    percentFull:
      totalCapacityMl > 0 ? (totalVolumeMl / totalCapacityMl) * 100 : null,
    latestReadingDate,
  };
}
