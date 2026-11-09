# Getting the data

Every path ends in the same place: a file the helper script reads. Data pulled through a Google Ads connection is saved as a CSV first and then loaded exactly as if the user had uploaded it, so everything downstream works the same way whichever path supplied it.

## Products

**Best: the feed Merchant Center reads**, or a Merchant Center product download. It has the exact item IDs, the brand, product type, variant attributes (colour, size, material) and product links. Accepted formats: Google Shopping XML, `.tsv`/`.txt`/`.csv`, `.xlsx`.

**With a Google Ads connection**, the product list can come from the account instead (run it once; this is the query the original skill was built on):

```
SELECT
  shopping_product.item_id,
  shopping_product.title,
  shopping_product.brand,
  shopping_product.product_type_level1,
  shopping_product.product_type_level2,
  shopping_product.category_level1,
  shopping_product.category_level2,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM shopping_product
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.clicks DESC
```

Use `shopping_product`, not `shopping_performance_view`: it returns only products that exist in Merchant Center today (no titles wasted on deleted products), and its `item_id` keeps Merchant Center's exact capitalisation. A product can appear once per country or channel; the script keeps the row with the most clicks. Save the rows as a CSV with these column names (`item_id`, `title`, `brand`, `product_type_level1`, ..., `impressions`, `clicks`, `conversions`) and pass it to `normalise` as the feed. This list has no links, colours or sizes, so when the user also has the feed file, use the feed for products and this query (or a report) for clicks: `normalise FEED --perf CLICKS.csv`.

**Clicks without a connection:** in Google Ads, a product-level report (Products, or a custom report with Item ID and Clicks) downloaded as CSV works with `--perf`. Its IDs are often lower case, so the script joins them to the feed ignoring case and always keeps the feed's IDs. If the user has no clicks data at all, ask them to name their best sellers.

**Not usable on its own:** a store's product export (for example a Shopify product CSV). It doesn't contain the IDs Merchant Center uses, so a supplemental feed built from it would match nothing. The `inspect` step warns about this.

## Search terms (the strongest source)

**With a Google Ads connection:**

```
SELECT
  search_term_view.search_term,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM search_term_view
WHERE segments.date DURING LAST_90_DAYS
  AND metrics.impressions > 10
ORDER BY metrics.impressions DESC
LIMIT 5000
```

This covers Standard Shopping and Search campaigns. For an account that runs mostly Performance Max, also run, per Performance Max campaign:

```
SELECT
  campaign_search_term_insight.category_label,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM campaign_search_term_insight
WHERE campaign.id = <campaign id>
  AND segments.date DURING LAST_30_DAYS
ORDER BY metrics.impressions DESC
```

These are search categories (groups of similar searches), not exact searches, but their labels are still search language. Save each result as a CSV and load it with `terms` (the script merges files and labels Performance Max categories). If a query fails or returns nothing, say so and use the manual path or skip; never guess search terms.

**Without a connection:** in Google Ads, open the search terms report (under Insights and reports), set the date range to the last 90 days, and download it as CSV. Google's download starts with two title lines and ends with total rows; the script skips both. If the menus have moved, the user can search the Google Ads help for "search terms report".

**Neither:** skip the source, say so plainly in your first progress line and in the delivery, and build titles from the other sources. Titles without search data are weaker; never present your own keyword ideas as search data.

## Keyword Planner (optional)

**With a connection that offers keyword ideas:** request ideas once per category, not per product, seeded with the category's product type, its 3 to 5 best search terms, and the URL of its top product. Save the ideas (keyword, average monthly searches, competition) as a CSV and load them with `planner --category "<category>"`.

**Without one:** the user can download ideas from Keyword Planner in Google Ads (Discover new keywords, then download as CSV). The download is usually a UTF-16, tab-separated file with title lines at the top; the script reads it as it comes. Accounts with little ad spend see volume ranges ("1K – 10K") instead of numbers; the script ranks by the lower end and says so.

**Neither:** skip it. Search terms and the website cover most of what titles need.

## The website

Read the store's homepage once, then one product page per category (the top product by clicks, or the first one). Not every product page: the category gives the context, and the product data gives the specifics. When a category mixes different kinds of product (a store's "Equipment" holding suitcases, duffels and daypacks), read one page per kind of product instead. If the suggested page is out of stock, sold out or thin, read another product in the same category.

- On Shopify stores, adding `.json` to a product URL (`/products/<handle>.json`, with any `?variant=` part removed) usually returns the product's data as clean JSON. It often holds little more than the feed's description, so when it's thin, read the page itself.
- If fetching pages is blocked or fails (sites often refuse automated reads), use web search for the store and its main products instead. Don't get stuck retrying blocked pages. Phrases found this way on other sites are recorded with the source `web_search`, not `website`.
- Take product facts and positioning only: what it is, who it's for, the benefits the store leads with, materials and specs. Ignore reviews, shipping, promotions and related products.
