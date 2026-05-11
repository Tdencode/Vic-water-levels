# Site audit — Phase 1

Per-company audit of where storage data lives, how it's served, and what it'll take to scrape.

**Status legend:**
- ✅ Easy — static HTML or JSON endpoint, low effort
- 🟡 Medium — likely a JSON endpoint reachable via DevTools, or some JS rendering
- 🔴 Hard — needs Playwright or no obvious dashboard
- ❓ Blocked — couldn't audit yet (WAF / 403 / timeout via WebFetch); needs a real httpx call from a browser-like client

> **Note on 403s.** Several sites returned 403 to the WebFetch tool. WebFetch uses a generic user agent that gets blocked by Cloudflare/Akamai-style WAFs. These sites are very likely scrapeable from `httpx` with a normal browser User-Agent. We'll re-check during adapter development.

---

## Key insight: target *storage managers*, not retailers

Our initial best-guess list mixed bulk water managers (who own the storages) with retailers (who buy from them). Rationale for swaps:

- **North East Water** is a retailer that on-sells water from **Goulburn-Murray Water**. Scraping G-MW already gives us NEW's data — no separate adapter needed.
- **Gippsland Water** was re-evaluated as a potential 8th source against `gippswater.com.au/water-and-waste/our-services/water-supply`. The page is served behind Akamai and 403s every requester we have available (curl, WebFetch, curl_cffi Chrome impersonation). See §8 — left documented but unimplemented. Their main proprietary storage (Moondarra, ~30 GL) is small; the shared Gippsland-region storages (Blue Rock, Lake Glenmaggie) are already captured under **Southern Rural Water**.
- **Central Highlands Water** (Ballarat region) manages its own storages and has a dedicated levels page.

**Confirmed list of 7 storage managers:**
1. Melbourne Water
2. Goulburn-Murray Water (G-MW) — also covers North East Water region
3. Barwon Water
4. GWMWater
5. Coliban Water
6. Southern Rural Water (SRW) — covers many Gippsland & Werribee storages
7. Central Highlands Water

**Aggregator decision:** BOM/DEECA aggregators were investigated but rejected for primary use — they don't update with sufficient daily granularity. Per-company scrapers it is. BOM may still be useful as a fallback for Coliban (whose own page is stale).

---

## 1. Melbourne Water ✅ (implemented)

- **Public page:** https://www.melbournewater.com.au/water-and-environment/water-management/water-storage-levels
- **Render:** Page is JS-loaded. The Vue app's `data-api-url` exposed a public AWS API Gateway: `https://api.melbournewater.com.au/water-storage`. JS bundle inspection found `/levels/day?searchDate=YYYY-MM-DD` returning a clean JSON document with all 10 catchments.
- **Endpoint used:** `GET https://api.melbournewater.com.au/water-storage/levels/day?searchDate=YYYY-MM-DD`
- **Response shape:**
  - `date` — authoritative reading date (the API echoes the latest available day if today's data isn't published yet)
  - `waterStorageLevels.catchmentStorageLevels.catchments[]` — per-reservoir `{ name, totalCapacity, currentCapacity, percentageFull, rainfallRecorded }`
- **Other discovered endpoints (not currently used):** `/levels/historical` (monthly averages back to 1948), `/levels/storage/day/file` (CSV download), `/levels/week`, `/levels/storage/week/file`.
- **Update cadence:** Daily, recorded 8am, refreshed early afternoon.
- **Coverage:** All 10 major reservoirs (Thomson, Cardinia, Upper Yarra, Sugarloaf, Silvan, Tarago, Yan Yean, Greenvale, Maroondah, O'Shannassy).

## 2. Goulburn-Murray Water ✅ (implemented — Waterline source)

- **Index page:** https://waterline.g-mwater.com.au/waterstatus/SSR/status.shtml
- **Render:** IIS-hosted static `.shtml` fragments — no JS execution required, no bot protection. The legacy table at `www.g-mwater.com.au/water-operations/storage-levels` has been retired in favour of Waterline; the new adapter scrapes Waterline directly for richer per-station daily series.
- **Two-step fetch:**
  1. `GET /SSR/status.shtml` — index page with a `Time of Report: DD/MM/YYYY HH:MM AEST` stamp and 26 `on_image_clicked('waterApp','./SSR/<basin>/storage/<station_id>//location_<id>.shtml')` JS hooks. Each storage's `<img title="<NAME>: 1 hr rainfall total">` carries the display name (we strip the colon-suffix and any trailing " Head Gauge").
  2. `GET /SSR/<basin>/storage/<id>//location_daily_<id>.shtml` — small `<table id="tableStyle7">` with columns Date/Time, Observed Level (m), Calculated Volume (ML), Percentage full (%). The latest non-placeholder row (table ends with `-` rows for future days) is the current reading.
- **Reading date:** constructed from the table's `DD-MM` column + year from the index's Time of Report stamp; handles year carry-over so December rows on a January report still resolve correctly.
- **Capacity:** not exposed in the daily table — derived algebraically as `volume / percent * 100` when percent is non-zero. Mathematically identical to the page's own FSL.
- **Storage slugs:** raw lowercase station codes (e.g. `g405259a`, `g10132`). Differ from the old adapter's slugs — old rows remain in Supabase as historical records, new readings flow into new rows.
- **Coverage:** 26 stations across 7 basins (broken, campaspe, goulburn, loddon, murray, ovens, uppermurray). 21 of those publish full volume + percent (the others — Lake Cooper, Greens Lake, Third Lake, Dartmouth Regulating Pondage, Evansford Reservoir — expose level only and are skipped). Includes all the previously-tracked majors: Dartmouth, Lake Hume, Lake Eildon, Lake Eppalock, Goulburn Weir, plus Yarrawonga Weir (Mulwala), Lake Buffalo, Lake William Hovell, Cairn Curran/Tullaroop/Laanecoorie/Newlyn/Hepburns, Lake Nillahcootie, Waranga Basin, and several mid-Murray off-river storages (Kow Swamp, Lake Charm, Lake Boga, Torrumbarry Weir).
- **Licence:** Waterline content is published under CC BY 4.0; attribution is shown in the homepage footer.
- **Bonus endpoints (not used):** RSS `/rss/levels.asp` and the mobile page `/mobile/storages.html` on the main G-MW domain — kept as backup options if Waterline ever changes structure.

## 3. Barwon Water 🟡 (implemented, but blocked from CI)

- **Public pages:** `/water-and-waste/water-storages/{geelong,colac,lorne,apollo-bay}`
- **Endpoint used:** `GET https://www.barwonwater.vic.gov.au/_webservices/json/waterstorage?region_name={region}` — discovered in the page bootstrap as the source for the `waterStoragesTable`/`waterStoragesStats`/`waterStoragesChart` widgets. Public HTML pages don't carry inline values; they XHR this endpoint client-side.
- **Response shape:** `reservoir_levels[]` with `location`, `present_volume`, `total_capacity`, `percentage_full` (all stringified). Each region also includes a roll-up row whose `location` ends with " total"/"Total"; the adapter skips these. Reading date is taken from the last entry of `water_storage_levels` (the actual measurement date — `date_updated` is the publish date, typically a day later).
- **Coverage:** 11 reservoirs (Geelong: West Barwon, Wurdee Boluc, Korweinguboora, Bostock, Stony Creek, Lal Lal share. Colac: West Gellibrand, Olangolah, No. 4 Basin, No. 5 Basin. Lorne: Allen). Apollo Bay's endpoint returns a backend-error envelope; the adapter tolerates this.
- **🟡 Cloudflare block from CI:** Cloudflare combines TLS fingerprinting (JA3) with **IP-reputation filtering**. From residential IPs the call works; from datacentre IPs (GitHub Actions, AWS, etc.) it 403s even with `curl_cffi` Chrome impersonation, cookie warmup, and a `chrome131 → chrome124 → chrome120` profile fallback. Public HTML pages on the same site also 403, and they have no inline data anyway. Confirmed BOM (Tableau Public, behind AWS WAF Captcha), Vic Open Data (only monthly + 7 months stale), and DEECA WMIS (custom KiWIS variant, half-day spike to reverse-engineer) all fail to provide a daily Barwon source.
- **Resolution:** The adapter now **swallows 403s as "unavailable from this network"** rather than failing the whole run. The CI job stays green, existing Barwon rows in Supabase remain the most-recent reading, and the homepage continues to show whatever Barwon data was last successfully written. To refresh Barwon data, run the adapter manually from a residential IP: `python -m scrapers.runner --company barwon-water`. If Cloudflare ever relaxes the block, the adapter resumes silently.
- **Notes:** Lal Lal is shared with Central Highlands Water — the published row shows Barwon's 16,793 ML share only, not the whole reservoir. Avoid double-counting with CHW's row.

## 4. GWMWater ✅ (implemented)

- **Public page:** https://www.gwmwater.org.au/reservoir-levels-and-other-information/reservoirs-level-summary
- **Render:** Static HTML — single `<table class="bwmtable">` with rows per reservoir and a "Total supply" footer row that we skip.
- **Reading date:** parsed from the `<h3 class="table_updated">Updated as of DD MMM YYYY</h3>` header.
- **Columns used:** Reservoir Name (col 0), Contents when full ML (col 2), Current contents ML (col 4), Current percent full (col 5).
- **Update cadence:** **Weekly** — Thursday-to-Wednesday window, uploaded Wednesday afternoon. Daily cron is still fine — `UNIQUE(storage_id, reading_date)` makes mid-week pulls a no-op.
- **Coverage:** All 10 reservoirs (Bellfield, Fyans, Lonsdale, Moora Moora, Rocklands, Taylors Lake, Toolondo, Wartook, Mt Cole, Green Lake). Green Lake is suffixed `^` on the page (footnoted as excluded from totals); the adapter strips the caret to keep slug stable.

## 5. Coliban Water ✅ (implemented)

- **Pages:** `https://coliban.com.au/about-us/our-reservoirs/{slug}/levels` for the 4 main reservoirs (Malmsbury, Lauriston, Upper Coliban, Lake Eppalock). The older `water-storage-data-and-information` page is stale (Aug 2021) — the per-reservoir pages under `/about-us/our-reservoirs` are the live ones.
- **Endpoint used:** `POST https://webserver.coliban.com.au/ResLevelsService/webplace.asmx/WaterStorageLevels` with JSON body `{"to","from","reservoir","granularity":"day"}`. Legacy ASP.NET ASMX, so the response wraps real JSON inside a top-level `"d"` string field.
- **Reservoir param:** free-text reservoir name from each chart's `data-params` attribute, **not** the URL slug — e.g. `upper coliban` (with space) for Upper Coliban Reservoir. Sending an unknown name silently returns the *combined* catchment numbers, so the slug→param map is hardcoded with a no-duplicate test.
- **Update cadence:** Malmsbury, Lauriston, Upper Coliban update daily; Lake Eppalock updates weekly. Adapter requests a 14-day window and reads the last entry of `waterStorageVolumes` so each reservoir reports its actual freshest reading.
- **Field-naming trap:** `waterStorageTotals.currentCapacity` is misleadingly the *current volume*; capacity lives in `totalCapacity`. The adapter reads volume + percent from the per-reading entry to avoid the trap.
- **Coverage:** 4 main Coliban reservoirs. Coliban operates ~35 storages overall but only these 4 have public live pages. Coliban's Lake Eppalock figure is their share (~55 GL) and coexists with G-MW's full-reservoir reading under different `company_slug`/`storage_slug` keys — no row collision.

## 6. Southern Rural Water ✅ (implemented)

- **Public pages:** `/water-and-storage/water-storages/{slug}` for the 7 reservoirs (Blue Rock Lake, Lake Glenmaggie, Lake Narracan, Melton Reservoir, Merrimu Reservoir, Pykes Creek Reservoir, Rosslynne Reservoir).
- **Render:** Each per-storage page renders a Highcharts chart fed by an XHR. The summary `/storage-levels` page itself only links out to per-storage pages — it has no values.
- **Endpoint used:** `POST https://www.srw.com.au/graphs/storage-chart/get-chart-data` with `reservoir=N` in the form body and `X-Requested-With: XMLHttpRequest` header (without it the Drupal route returns HTML 404).
- **Reservoir IDs:** stable 1–7 mapping discovered from each per-storage page's `data-reservoir-id` attribute and hardcoded in the adapter to skip 7 extra page fetches per run.
- **Response shape:** Highcharts series array. Series 0 ("Storage Level") is daily volume in ML, with a trailing ~80-day axis-padding tail of `[future_ts, 0]` points; the parser walks backwards to the last non-zero entry. Series 1 ("Full Capacity") gives capacity history; the last entry is current capacity. Percent-full is computed.
- **Coverage:** All 7 SRW major storages.
- **MySRW decommission caveat:** the page mentions "MySRW platform decommissioned in May 2026" but this refers to the customer-accounts portal at mysrw.com.au — the storage-levels pages on srw.com.au are unaffected.

## 7. Central Highlands Water ✅ (implemented)

- **Public page:** https://www.chw.net.au/community/water-storage-levels (with `?Area=N` for N=0..3)
- **Render:** Static HTML behind Cloudflare. Same Chrome-shaped header set added for Barwon passes the JS challenge here too.
- **Areas:** 0=Ballarat, 1=Maryborough, 2=Daylesford, 3=Regional. Each renders one `<table class="chw-data-table">` preceded by a header `<div>CHW Reservoir Water Storages, as at DD MMM YYYY</div>` (used as the reading date).
- **Total-row handling:** rows whose name ends with the word `Total` (or `(Total)`) are skipped — covers `Ballarat Total`, `Maryborough Total`, `Daylesford Total`, and the `Lal Lal Reservoir (Total)` whole-reservoir aggregate.
- **Coverage:** 25 reservoirs across all 4 areas, including CHW's 35,670 ML Lal Lal share (`Lal Lal Reservoir (CHW)`).
- **Lal Lal de-duplication:** CHW's row and Barwon Water's share row have distinct slugs (`lal-lal-reservoir-chw` vs `lal-lal-reservoir-barwon-water-s-share`), so the two adapters can both run without double-counting. The whole-reservoir total row on CHW's page is filtered out.

## 8. Gippsland Water ❓ (blocked — not implemented)

- **Public page:** https://www.gippswater.com.au/water-and-waste/our-services/water-supply
- **Render:** Served behind **Akamai** (`server: AkamaiGHost`). Returns HTTP 403 to plain `curl`, to the Claude WebFetch tool, and to `curl_cffi` Chrome impersonation across `chrome131`/`chrome124`/`chrome120` profiles. Sub-paths under `gippswater.com.au` timed out entirely from this network after the initial 403 round — Akamai appears to be combining fingerprint + IP-reputation filters more aggressively than the Cloudflare blocks we've worked around elsewhere.
- **Investigated alternatives:**
  - **DEECA Current Water Snapshot CSVs** at https://www.water.vic.gov.au/our-programs/water-monitoring-and-reporting/current-water-snapshot — landing page is reachable but the three weekly CSVs (northern / southern-and-western / metro-melbourne) themselves return a Cloudflare managed-challenge HTML payload to non-browser clients.
  - **Wayback Machine** — blocked by egress policy from this environment.
- **Status:** No machine-parseable source for Gippsland's own storage figures could be confirmed from CI/sandbox infrastructure. Their main proprietary storage (Moondarra, ~30 GL) remains uncovered. Shared Gippsland-region storages (Blue Rock, Lake Glenmaggie) are already captured under the Southern Rural Water adapter, so headline regional coverage is intact.
- **Resume conditions:** any of (a) Akamai relaxing the IP-reputation filter so `curl_cffi` chromeNNN works from CI, (b) a public JSON/API endpoint surfaced by Gippsland Water, or (c) a reliable workaround on the DEECA snapshot CSVs (e.g. an authenticated API key path) would unblock implementation. The adapter pattern is well-established — copying `barwon_water.py` for impersonation + graceful 403 degradation is the right scaffold when that day comes.

---

## Aggregator sources investigated

These are state-wide datasets. Worth evaluating because **one good aggregator could replace several per-company adapters**.

### Bureau of Meteorology Water Data Online (KiWIS)

- **Dashboard:** https://www.bom.gov.au/water/dashboards/ (Tableau-rendered, hard to scrape directly)
- **API:** BOM exposes a **KISTERS KiWIS QueryServices** API at `http://www.bom.gov.au/waterdata/services` (mentioned on the page). KiWIS is a documented standard for hydrological data — supports queries for stations, parameters, time series. Likely the cleanest single source.
- **Coverage:** Includes major Victorian storages already (Coliban explicitly cites it). Probably covers most of our targets.
- **Plan:** Spike a `kiwis_get_station_list` + `kiwis_get_timeseries_values` call for one Victorian storage and see what comes back. If it works, this could become the **primary source for Coliban + a fallback for everything**.

### DEECA Water Measurement Information System (WMIS)

- **URL:** https://data.water.vic.gov.au/
- **Status:** WebFetch returned a near-empty page; the site is a SPA. WMIS is a known DEECA platform for water-monitoring data; it should have an API but documentation wasn't retrievable.
- **Plan:** Look for `data.water.vic.gov.au/static.htm` documentation page or an OpenAPI/Swagger endpoint when implementing.

### Vic Government "Current water snapshot"

- https://www.water.vic.gov.au/our-programs/water-monitoring-and-reporting/current-water-snapshot
- Couldn't audit (403). News articles cite it as the source for state-level aggregate %-full figures. Likely synthesises BOM/DEECA data.

---

## Recommended adapter build order

Build easiest-first to derisk the framework, then tackle harder ones:

| # | Company | Difficulty | Source approach |
|---|---------|------------|-----------------|
| 1 | Goulburn-Murray Water | ✅ Done | Two-step scrape of `waterline.g-mwater.com.au/waterstatus/`: index page (`/SSR/status.shtml`) → 26 per-station daily tables; capacity derived from volume ÷ percent |
| 2 | Melbourne Water | ✅ Done | Public JSON API at `api.melbournewater.com.au/water-storage/levels/day` |
| 3 | GWMWater | ✅ Done | Static HTML `table.bwmtable` on summary page |
| 4 | Barwon Water | 🟡 Done, blocked from CI | Public JSON web service `/_webservices/json/waterstorage?region_name=…` (Cloudflare IP-reputation block on datacentre runners — adapter swallows 403s; refresh from a residential IP) |
| 5 | Central Highlands Water | ✅ Done | Static HTML across 4 area pages (`?Area=0..3`); Cloudflare-gated, handled by shared headers |
| 6 | Southern Rural Water | ✅ Done | POST `/graphs/storage-chart/get-chart-data?reservoir=N` per per-storage page; walk Highcharts series backwards past trailing zero-padding |
| 7 | Coliban Water | ✅ Done | POST `webserver.coliban.com.au/ResLevelsService/webplace.asmx/WaterStorageLevels` per reservoir; ASMX `{"d":"<json>"}` envelope |

---

## Daily cron note

GWMWater is weekly (uploaded Wed afternoon); G-MW and Melbourne Water are daily; others to be confirmed during adapter dev. The daily cron is fine — `UNIQUE(storage_id, reading_date)` deduplicates so weekly sources just no-op on most days.
