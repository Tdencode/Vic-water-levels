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

## 3. Barwon Water ❓

- **Page:** https://www.barwonwater.vic.gov.au/water-and-waste/water-storages/geelong-region
- **Render:** Couldn't audit — 403 Forbidden via WebFetch (likely WAF).
- **Update cadence:** Unknown. Recent news articles report combined %-full figures, suggesting a real dashboard exists.
- **Plan:** Re-fetch with `httpx` + browser User-Agent during adapter dev. If still blocked, fall back to Playwright. If still no dashboard, news articles or annual reports may be the only public source.

## 4. GWMWater 🟡

- **Page:** https://www.gwmwater.org.au/reservoir-levels-and-other-information/reservoir-levels
- **Summary page:** https://www.gwmwater.org.au/component/content/article/52-reservoir-level-summary?Itemid=253
- **Render:** Static HTML, but the parent URL only describes the system; actual data lives on the summary page (need to fetch that next).
- **Update cadence:** **Weekly** — Thursday-to-Wednesday window, uploaded Wednesday afternoon. Daily scrape will be wasteful → de-dupe by `(storage_id, reading_date)` is essential.
- **Plan:** Fetch the summary page directly. Parse table.

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

## 7. Central Highlands Water ❓ (proposed swap)

- **Page:** https://www.chw.net.au/community/water-storage-levels
- **Render:** Couldn't audit — 403 to WebFetch.
- **Plan:** Re-check with httpx + real UA during adapter dev.

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
| 3 | GWMWater | 🟡 Med | Static HTML on summary page (de-dupe weekly) |
| 4 | Barwon Water | ❓ TBD | httpx + real UA; if blocked, Playwright |
| 5 | Central Highlands Water | ❓ TBD | httpx + real UA |
| 6 | Southern Rural Water | 🟡 Med | XHR inspection; watch for MySRW decommission |
| 7 | Coliban Water | 🔴 Hard | BOM KiWIS API (their own page is stale) |

---

## Daily cron note

GWMWater is weekly (uploaded Wed afternoon); G-MW and Melbourne Water are daily; others to be confirmed during adapter dev. The daily cron is fine — `UNIQUE(storage_id, reading_date)` deduplicates so weekly sources just no-op on most days.
