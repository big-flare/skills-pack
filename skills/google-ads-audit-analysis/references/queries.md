# The data: queries and how to save them

Every route ends in the same place: one result per query, read by `audittool.py load`. The Google Ads Script (`scripts/export-data.js`) runs exactly these queries and saves them all in one file. With a Google Ads connection, run them yourself and save each result as described below. Keep this file and the script in step: they are the same list.

## Dates

Two windows, both ending on the report's end date:

- `{FROM}` to `{TO}`: the report's date range (the one the user confirmed).
- `{LAST_YEAR}-01-01` to `{TO}`: the Account calendar, from 1 January of the year before `{TO}`'s year. `{THIS_YEAR}` is `{TO}`'s year.

## Saving results from a connection

1. Make a folder, for example `<run>/raw/`.
2. Run each query below for the account and save the result as `<query name>.json` (for example `campaigns_daily.json`). Save what the connection returned, complete: the rows list, or the whole response. Nested rows (`{"campaign": {"name": ...}}`), flat rows (`"campaign.name"`), camelCase or snake_case names, and enum names or numbers all load the same. A CSV whose headers are the field paths works too.
3. Also run this, saved as `account_info.json`, so the report knows the account's name and currency:

```sql
SELECT customer.id, customer.descriptive_name, customer.currency_code FROM customer
```

4. Load the folder: `python3 <skill-dir>/scripts/audittool.py load <run>/raw --run <run> --from {FROM} --to {TO}`.

**Large accounts.** Daily campaign rows, products and keywords can run to tens of thousands of rows. If the connection returns a result too large to read, or saves it to a file, use that file directly; never copy rows by hand. If results keep overflowing, switch to the Google Ads Script route: it writes everything straight to one file.

**A query fails.** Report the error to the user. `campaigns_daily` is the only one the workbook can't do without; for any other, carry on and say which tab is missing.

## The queries

### `account_monthly`

Account tab: every month of last year and this year, all campaign types.

```sql
SELECT segments.month, metrics.conversions, metrics.cost_micros, metrics.conversions_value,
       metrics.conversions_value_by_conversion_date, metrics.search_impression_share,
       metrics.search_rank_lost_impression_share, metrics.search_budget_lost_impression_share
FROM customer
WHERE segments.date BETWEEN '{LAST_YEAR}-01-01' AND '{TO}'
```

### `account_total_last_year`

Account tab: the Last year total row. Impression share can't be added up from months, so the totals are their own queries.

```sql
SELECT metrics.conversions, metrics.cost_micros, metrics.conversions_value,
       metrics.conversions_value_by_conversion_date, metrics.search_impression_share,
       metrics.search_rank_lost_impression_share, metrics.search_budget_lost_impression_share
FROM customer
WHERE segments.date BETWEEN '{LAST_YEAR}-01-01' AND '{LAST_YEAR}-12-31'
```

### `account_total_this_year`

Account tab: the This year (YTD) total row.

```sql
SELECT metrics.conversions, metrics.cost_micros, metrics.conversions_value,
       metrics.conversions_value_by_conversion_date, metrics.search_impression_share,
       metrics.search_rank_lost_impression_share, metrics.search_budget_lost_impression_share
FROM customer
WHERE segments.date BETWEEN '{THIS_YEAR}-01-01' AND '{TO}'
```

### `account_total_both`

Account tab: the Last year + this year total row.

```sql
SELECT metrics.conversions, metrics.cost_micros, metrics.conversions_value,
       metrics.conversions_value_by_conversion_date, metrics.search_impression_share,
       metrics.search_rank_lost_impression_share, metrics.search_budget_lost_impression_share
FROM customer
WHERE segments.date BETWEEN '{LAST_YEAR}-01-01' AND '{TO}'
```

### `account_network_monthly`

Search Volume tab: Google Search impressions by month, for eligible impressions.

```sql
SELECT segments.month, segments.ad_network_type, metrics.impressions
FROM campaign
WHERE segments.date BETWEEN '{LAST_YEAR}-01-01' AND '{TO}'
```

### `campaigns_daily`

Channel Split and Campaign tabs. **Required**: every other tab is optional.

```sql
SELECT campaign.id, campaign.name, campaign.advertising_channel_type, segments.date,
       segments.ad_network_type, metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM campaign
WHERE segments.date BETWEEN '{FROM}' AND '{TO}'
```

### `pmax_shopping_daily`

Channel Split: the part of Performance Max that is Shopping ads.

```sql
SELECT campaign.id, campaign.advertising_channel_type, segments.date, segments.ad_network_type,
       metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM shopping_performance_view
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' AND segments.date BETWEEN '{FROM}' AND '{TO}'
```

### `assets`

Assets tab.

```sql
SELECT asset_group_asset.field_type, asset_group_asset.source, asset_group_asset.resource_name, asset.id,
       asset.name, asset.type, asset.text_asset.text, asset.youtube_video_asset.youtube_video_id,
       asset.youtube_video_asset.youtube_video_title, asset.image_asset.full_size.url, metrics.impressions,
       metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM asset_group_asset
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' AND segments.date BETWEEN '{FROM}' AND '{TO}'
```

### `products`

Products and Product Families tabs: performance by product.

```sql
SELECT campaign.id, campaign.advertising_channel_type, segments.ad_network_type, segments.product_item_id,
       segments.product_title, segments.product_feed_label, metrics.impressions, metrics.clicks,
       metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM shopping_performance_view
WHERE campaign.advertising_channel_type IN ('PERFORMANCE_MAX', 'SHOPPING') AND segments.date BETWEEN '{FROM}' AND '{TO}'
```

### `product_inventory`

Products tabs: every product listed today, including Zombies with no spend.

```sql
SELECT shopping_product.item_id, shopping_product.title, shopping_product.status,
       shopping_product.feed_label, shopping_product.brand, shopping_product.product_type_level1,
       shopping_product.product_type_level2
FROM shopping_product
```

### `pmax_search_terms`

Keyword Gap tab: Performance Max search terms that converted.

```sql
SELECT campaign.id, campaign_search_term_view.search_term, metrics.clicks, metrics.impressions,
       metrics.conversions, metrics.cost_micros, metrics.conversions_value
FROM campaign_search_term_view
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' AND metrics.conversions > 0 AND segments.date BETWEEN '{FROM}' AND '{TO}'
```

### `search_keywords`

Keyword Gap tab: every Search keyword and its status. No date filter, on purpose: paused and removed keywords count.

```sql
SELECT campaign.id, campaign.status, ad_group.status, ad_group_criterion.keyword.text,
       ad_group_criterion.keyword.match_type, ad_group_criterion.status,
       ad_group_criterion.system_serving_status, ad_group_criterion.primary_status,
       ad_group_criterion.primary_status_reasons
FROM keyword_view
WHERE campaign.advertising_channel_type = 'SEARCH' AND ad_group_criterion.negative = FALSE
```

## Keyword Planner (Search Volume tab, optional)

Keyword Planner's monthly volumes can't come from a Google Ads Script. Two ways to get them, for a short list of the store's main non-brand category keywords (5 to 15, in the market's language, no close duplicates):

- **A connection that offers Keyword Planner historical metrics** (often called "keyword historical metrics" or "generate keyword historical metrics"): request monthly volumes for the keywords, the store's main countries and language, from January last year to the latest month. Save the response as JSON and pass it to `planner`.
- **A Keyword Planner download**: in Google Ads, Tools > Planning > Keyword Planner > Get search volume and forecasts. Paste the keywords, set the location and language, open Historical metrics, set the date range from January last year to the latest month, and download it. Pass the file to `planner` as it comes (Google's UTF-16, tab-separated format is fine).

```
python3 <skill-dir>/scripts/audittool.py planner <file> --run <run> --market "United Kingdom" --language English
```
