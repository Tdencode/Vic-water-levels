-- Remove de-listed storages and their readings (cascades via FK).
-- Each DELETE keeps only the specific slugs that are still scraped;
-- everything else is dropped so the latest_readings view stays clean.

-- Goulburn-Murray Water: keep 8 named storages only.
DELETE FROM water_levels.storages
WHERE company_slug = 'goulburn-murray-water'
  AND slug NOT IN (
    'dartmouthdam',
    'humedam',
    'lakeeildon',
    'warangabasin',
    'lakeeppalock',
    'cairncurranreservoir',
    'nillahcootie',
    'tullaroopreservoir'
  );

-- Barwon Water: keep Geelong region storages only.
DELETE FROM water_levels.storages
WHERE company_slug = 'barwon-water'
  AND slug NOT IN (
    'west-barwon-reservoir',
    'wurdee-boluc-reservoir',
    'korweinguboora-reservoir',
    'bostock-reservoir',
    'stony-creek-reservoirs',
    'lal-lal-reservoir-barwon-water-s-share'
  );

-- Central Highlands Water: keep Ballarat (Area 0) storages only.
DELETE FROM water_levels.storages
WHERE company_slug = 'central-highlands-water'
  AND slug NOT IN (
    'lal-lal-reservoir-chw',
    'white-swan-reservoir',
    'moorabool-reservoir',
    'gong-gong-reservoir',
    'wilsons-reservoir',
    'cosgrave-reservoir',
    'beales-reservoir',
    'kirks-reservoir',
    'pincotts-reservoir',
    'newlyn-reservoir'
  );

-- Southern Rural Water: remove Narracan and Rosslynne.
DELETE FROM water_levels.storages
WHERE company_slug = 'southern-rural-water'
  AND slug IN ('lake-narracan', 'rosslynne-reservoir');

-- Coliban Water: remove Lake Eppalock (tracked by Goulburn-Murray Water).
DELETE FROM water_levels.storages
WHERE company_slug = 'coliban-water'
  AND slug = 'lake-eppalock';
