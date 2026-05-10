"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

// Cycle through Light → Dark → System. We render an empty placeholder on
// the first paint to avoid a hydration mismatch — the resolved theme isn't
// known until next-themes reads localStorage on the client.
export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const baseClass =
    "inline-flex h-9 w-9 items-center justify-center rounded-full " +
    "border border-slate-200 bg-white text-slate-600 shadow-sm " +
    "transition-colors duration-150 " +
    "hover:bg-slate-50 hover:text-slate-900 " +
    "focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 " +
    "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 " +
    "dark:hover:bg-slate-800 dark:hover:text-slate-50";

  if (!mounted) {
    return (
      <span
        className={baseClass}
        aria-hidden="true"
        // Reserve space so the header doesn't shift on first paint.
      />
    );
  }

  const isDark = resolvedTheme === "dark";
  const next = isDark ? "light" : "dark";
  const label = isDark ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      title={`Theme: ${theme ?? "system"} — click to switch`}
      aria-label={label}
      className={baseClass}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}
