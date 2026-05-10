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
- **Gippsland Water** publishes only news articles and an annual outlook PDF — no live dashboard. Their main storage (Moondarra, ~30 GL) is small. Most Gippsland-region storages they share are managed by **Southern Rural Water** (Blue Rock, Glenmaggie).
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

## 2. Goulburn-Murray Water ✅ (implemented)

- **Page:** https://www.g-mwater.com.au/water-operations/storage-levels
- **Render:** **Static HTML table.** All 23 storages with name, volume (ML), capacity (ML), % full. Confirmed via WebFetch.
- **Update cadence:** Daily. Last update visible in the page (e.g. `08/05/2026`).
- **Storages (sample):** Dartmouth Dam, Hume Dam, Lake Eildon, Lake Eppalock, plus 19 others across 7 regions (Murray, Ovens, Broken, Goulburn, Campaspe, Loddon, Bullarook Creek).
- **Bonus endpoints:**
  - RSS feed: `/rss/levels.asp` — may give us a clean parseable feed
  - Waterline dashboard: https://waterline.g-mwater.com.au/waterstatus/ — likely a JSON-backed app for deeper data
  - Mobile page: https://www.g-mwater.com.au/mobile/storages.html — simpler markup, good fallback
- **Plan:** Parse the static table on the main URL. Try RSS as alternative source for resilience. **Easiest adapter — build first.**

## 3. Barwon Water ✅ (implemented)

- **Public pages:** `/water-and-waste/water-storages/{geelong,colac,lorne,apollo-bay}`
- **Render:** Pages are behind Cloudflare bot protection — the default JS-challenge interrupts plain `httpx`/`curl` requests. Sending a full Chrome-shaped header set (User-Agent, Accept-Language, `Sec-Ch-Ua*`, `Sec-Fetch-*`, `Upgrade-Insecure-Requests`) is enough to pass; this is now the default for the shared HTTP client.
- **Endpoint used:** `GET https://www.barwonwater.vic.gov.au/_webservices/json/waterstorage?region_name={region}` — discovered in the page bootstrap as the source for the `waterStoragesTable`/`waterStoragesStats`/`waterStoragesChart` widgets.
- **Response shape:** `reservoir_levels[]` with `location`, `present_volume`, `total_capacity`, `percentage_full` (all stringified). Each region also includes a roll-up row whose `location` ends with " total"/"Total"; the adapter skips these. Reading date is taken from the last entry of `water_storage_levels` (the actual measurement date — `date_updated` is the publish date, typically a day later).
- **Coverage:** 11 reservoirs live (Geelong: West Barwon, Wurdee Boluc, Korweinguboora, Bostock, Stony Creek, Lal Lal share. Colac: West Gellibrand, Olangolah, No. 4 Basin, No. 5 Basin. Lorne: Allen). Apollo Bay's endpoint currently returns a backend-error envelope; the adapter tolerates this and skips the region.
- **Notes:** Lal Lal is shared with Central Highlands Water — the published row shows Barwon's 16,793 ML share only, not the whole reservoir. Avoid double-counting when CHW's adapter lands.

## 4. GWMWater ✅ (implemented)

- **Public page:** https://www.gwmwater.org.au/reservoir-levels-and-other-information/reservoirs-level-summary
- **Render:** Static HTML — single `<table class="bwmtable">` with rows per reservoir and a "Total supply" footer row that we skip.
- **Reading date:** parsed from the `<h3 class="table_updated">Updated as of DD MMM YYYY</h3>` header.
- **Columns used:** Reservoir Name (col 0), Contents when full ML (col 2), Current contents ML (col 4), Current percent full (col 5).
- **Update cadence:** **Weekly** — Thursday-to-Wednesday window, uploaded Wednesday afternoon. Daily cron is still fine — `UNIQUE(storage_id, reading_date)` makes mid-week pulls a no-op.
- **Coverage:** All 10 reservoirs (Bellfield, Fyans, Lonsdale, Moora Moora, Rocklands, Taylors Lake, Toolondo, Wartook, Mt Cole, Green Lake). Green Lake is suffixed `^` on the page (footnoted as excluded from totals); the adapter strips the caret to keep slug stable.

## 5. Coliban Water 🔴

- **Page:** https://coliban.com.au/water-storage-data-and-information
- **Render:** Static HTML, **but data is stale (last updated Aug 2021).** The page itself directs users to BOM dashboards for current numbers.
- **Reservoirs mentioned:** Upper Coliban, Lauriston, Malmsbury, McCay, Barkers Creek, Sandhurst, Spring Gully (no current values).
- **External sources cited:**
  - BOM Water Storages: `https://www.bom.gov.au/water/dashboards/#/water-storages/sites/state?storage=Malmsbury`
  - DEECA WMIS: `https://data.water.vic.gov.au/`
- **Plan:** Don't scrape coliban.com.au. Use BOM Water Data Online (KiWIS API) instead — see "BOM aggregator" below.

## 6. Southern Rural Water 🟡 (proposed swap)

- **Page:** https://www.srw.com.au/water-and-storage/water-storages/storage-levels
- **Render:** Page lists 7 storages but values aren't in static HTML — likely JS-loaded chart.
- **Storages:** Blue Rock Lake, Lake Glenmaggie, Lake Narracan, Melton Reservoir, Merrimu Reservoir, Pykes Creek Reservoir, Rosslynne Reservoir.
- **⚠️ Risk:** SRW page mentions the **MySRW platform will be decommissioned in May 2026** (this month) and data is moving to a "Prices and Forms" page. Need to monitor this.
- **Plan:** Investigate XHR calls or scrape per-storage pages.

## 7. Central Highlands Water ✅ (implemented)

- **Public page:** https://www.chw.net.au/community/water-storage-levels (with `?Area=N` for N=0..3)
- **Render:** Static HTML behind Cloudflare. Same Chrome-shaped header set added for Barwon passes the JS challenge here too.
- **Areas:** 0=Ballarat, 1=Maryborough, 2=Daylesford, 3=Regional. Each renders one `<table class="chw-data-table">` preceded by a header `<div>CHW Reservoir Water Storages, as at DD MMM YYYY</div>` (used as the reading date).
- **Total-row handling:** rows whose name ends with the word `Total` (or `(Total)`) are skipped — covers `Ballarat Total`, `Maryborough Total`, `Daylesford Total`, and the `Lal Lal Reservoir (Total)` whole-reservoir aggregate.
- **Coverage:** 25 reservoirs across all 4 areas, including CHW's 35,670 ML Lal Lal share (`Lal Lal Reservoir (CHW)`).
- **Lal Lal de-duplication:** CHW's row and Barwon Water's share row have distinct slugs (`lal-lal-reservoir-chw` vs `lal-lal-reservoir-barwon-water-s-share`), so the two adapters can both run without double-counting. The whole-reservoir total row on CHW's page is filtered out.

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
| 1 | Goulburn-Murray Water | ✅ Done | Parse static HTML table at `/water-operations/storage-levels` |
| 2 | Melbourne Water | ✅ Done | Public JSON API at `api.melbournewater.com.au/water-storage/levels/day` |
| 3 | GWMWater | ✅ Done | Static HTML `table.bwmtable` on summary page |
| 4 | Barwon Water | ✅ Done | Public JSON web service `/_webservices/json/waterstorage?region_name=…` (Cloudflare needs Chrome-shaped headers — now default in shared client) |
| 5 | Central Highlands Water | ✅ Done | Static HTML across 4 area pages (`?Area=0..3`); Cloudflare-gated, handled by shared headers |
| 6 | Southern Rural Water | 🟡 Med | XHR inspection; watch for MySRW decommission |
| 7 | Coliban Water | 🔴 Hard | BOM KiWIS API (their own page is stale) |

---

## Daily cron note

GWMWater is weekly (uploaded Wed afternoon); G-MW and Melbourne Water are daily; others to be confirmed during adapter dev. The daily cron is fine — `UNIQUE(storage_id, reading_date)` deduplicates so weekly sources just no-op on most days.
