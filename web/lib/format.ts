// Formatting helpers shared between the home page and any future detail pages.

export function formatVolume(ml: number | null | undefined): string {
  if (ml == null) return "—";
  if (ml >= 1_000_000) return `${(ml / 1_000_000).toFixed(2)} TL`;
  if (ml >= 1_000) return `${(ml / 1_000).toFixed(1)} GL`;
  return `${Math.round(ml).toLocaleString("en-AU")} ML`;
}

// Always display in GL — for statewide/regional aggregate callout cards.
export function formatVolumeGL(ml: number | null | undefined): string {
  if (ml == null) return "—";
  return `${(ml / 1_000).toFixed(1)} GL`;
}

// Always display in ML — for individual storage rows in the table.
export function formatVolumeML(ml: number | null | undefined): string {
  if (ml == null) return "—";
  return `${Math.round(ml).toLocaleString("en-AU")} ML`;
}

export function formatPercent(pct: number | null | undefined): string {
  if (pct == null) return "—";
  return `${pct.toFixed(1)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// Map a percent-full to a Tailwind colour class for the progress bar fill.
// Same thresholds for the bar and the badge so the UI reads consistently:
// red < 30, amber 30-70, sky >= 70. Vibrant fill colours read fine on
// either background; only the muted "no data" track needs a dark variant.
export function fillColorClass(pct: number | null | undefined): string {
  if (pct == null) return "bg-slate-300 dark:bg-slate-700";
  if (pct < 30) return "bg-red-500";
  if (pct < 70) return "bg-amber-500";
  return "bg-sky-500";
}

export function fillTextClass(pct: number | null | undefined): string {
  if (pct == null) return "text-slate-500 dark:text-slate-400";
  if (pct < 30) return "text-red-700 dark:text-red-400";
  if (pct < 70) return "text-amber-700 dark:text-amber-400";
  return "text-sky-700 dark:text-sky-400";
}
