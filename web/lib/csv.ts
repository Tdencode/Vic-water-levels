// CSV export helpers. RFC-4180 escaping: cells containing comma, quote,
// or newline get wrapped in double quotes with embedded quotes doubled.

function csvEscape(value: unknown): string {
  if (value == null) return "";
  const s = String(value);
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function rowsToCsv(headers: string[], rows: unknown[][]): string {
  const lines = [headers.map(csvEscape).join(",")];
  for (const row of rows) {
    lines.push(row.map(csvEscape).join(","));
  }
  // Trailing newline keeps Excel and Numbers happy.
  return lines.join("\n") + "\n";
}

export function downloadCsv(filename: string, csv: string): void {
  // BOM keeps Excel's auto-detection happy with UTF-8 (Lake Eppalock,
  // Mt Cole, etc. don't use non-ASCII characters today, but this is
  // cheap insurance for any future names that do).
  const blob = new Blob(["﻿", csv], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Defer revoke until after the browser kicks the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}
