import { createClient } from "@supabase/supabase-js";

// We expose the URL and anon key as NEXT_PUBLIC_ env vars so the same
// constants work in Server Components, Route Handlers and (future) Client
// Components. The anon key only has the SELECT grants from
// supabase/migrations/20260510000000_create_water_levels_schema.sql; never
// put the service_role key here.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY. " +
      "Copy web/.env.local.example to web/.env.local and fill it in.",
  );
}

// Pin the client to the water_levels Postgres schema; without this it
// defaults to `public` and our tables aren't there.
export const supabase = createClient(url, anonKey, {
  db: { schema: "water_levels" },
  auth: { persistSession: false },
});
