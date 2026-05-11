import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

// localStorage-backed Set of strings, with safe SSR fallbacks.
//
// The setter mirrors React's useState shape (accepts a Set or an updater
// function) so callers can do `setHidden((prev) => ...)` naturally.
//
// Reads synchronously on first render via lazy initial state so the UI
// reflects saved preferences immediately (no "all visible" flash before
// the saved hides apply). Writes happen via useEffect so the initial
// load doesn't double-persist.
//
// The key should include a version suffix (`vic-water:hidden-regions:v1`)
// so a future schema change can introduce :v2 and orphan the old data
// instead of mis-parsing it.
export function usePersistentStringSet(
  key: string,
): [Set<string>, Dispatch<SetStateAction<Set<string>>>] {
  const [value, setValue] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set();
    try {
      const raw = window.localStorage.getItem(key);
      if (!raw) return new Set();
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return new Set();
      return new Set(parsed.filter((s): s is string => typeof s === "string"));
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify([...value]));
    } catch {
      // Quota exceeded, private mode, etc. — silently ignore; the in-memory
      // state still works for the rest of the session.
    }
  }, [key, value]);

  return [value, setValue];
}
