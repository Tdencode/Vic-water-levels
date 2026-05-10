export type SortDir = "asc" | "desc";

export function compareNullsLast(
  a: string | number | null | undefined,
  b: string | number | null | undefined,
  dir: SortDir,
): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  const cmp = typeof a === "number" && typeof b === "number"
    ? a - b
    : String(a).localeCompare(String(b));
  return dir === "asc" ? cmp : -cmp;
}

export function sortBy<T>(
  rows: readonly T[],
  pick: (row: T) => string | number | null | undefined,
  dir: SortDir,
): T[] {
  return [...rows].sort((a, b) => compareNullsLast(pick(a), pick(b), dir));
}
