# Google Merchant Center rules this skill follows

Read this before writing the end-of-run instructions, and whenever a user asks why a rule exists. Every rule below comes from Google's own help pages (listed at the bottom, checked November 2026). Google changes these pages; if a user reports a rejection that contradicts this file, trust the live page and tell the user.

## The `title` attribute

- **Length:** 1 to 150 characters. Google truncates anything longer.
- **What shoppers see:** usually only the first 70 or fewer characters, depending on screen size. Google's advice is to put the most important details first.
- **Variants:** add the distinguishing details of each variant to its title (for example colour and size), and also send them in their own attributes (`color`, `size`, `age_group`). Details with no attribute of their own, such as flavour, go only in the title.
- **Brand:** add the product's brand name if it's a differentiating factor. For stores that sell many brands, adding the brand helps shoppers understand who makes the product.
- **No promotional text.** Don't add price, sale price, sale dates, shipping, delivery date, other time-related information, or your company's name. Those belong in their own attributes.
- **No capitals for emphasis.** Standard abbreviations (USB, LED, UK) are fine.
- **No gimmicks:** no all caps, symbols, HTML tags, extra white space, or foreign characters used to grab attention.
- **Language:** the title must be in the data source's language. Foreign words only when they are well understood.

**The company-name rule and the brand at the end.** When a store sells its own brand, the store's name is the product's brand, which Google asks you to include, so this skill ends every title with it. When a store resells other brands, the product's brand goes in the first half of the title and the store's own name is left out, because that is "your company's name". The user can choose to add it anyway (`--end-brand`); tell them it goes against Google's written rule.

## AI-written titles: `structured_title`

Google requires titles created with generative AI to be declared:

- AI-generated titles must use the `structured_title` attribute, with the `digital_source_type` sub-attribute set to `trained_algorithmic_media` and the text in the `content` sub-attribute (1 to 150 characters).
- If a product has both `title` and `structured_title`, Google uses only `title`.

In a text file the value is the source type, a colon, then the text in double quotes, with any double quote inside the text doubled:

```
trained_algorithmic_media:"The text of the title, with ""quotes"" doubled."
```

**What this skill does about it:** the supplemental feed carries three columns, `id`, `title` and `structured_title`, and both text columns hold the same new title. The `title` column is what replaces the old title (because when both exist, Google uses `title`). The `structured_title` column declares the title as AI-generated, which is what Google's AI-content rule asks for. Sending only `structured_title` would not work: the product's original `title` from the primary feed would still win.

If a user's tool cannot take the third column, a two-column file (`id`, `title`) still replaces the titles, but it does not declare them as AI-generated. Tell the user that plainly and let them decide; never drop the column silently. Titles the user edited in the review workbook started as AI-written, so they keep the declaration.

## The `id` attribute and matching

- IDs are 1 to 50 characters, case-sensitive, and should never change once assigned.
- A supplemental data source matches products by `id`. The match must be exact, and IDs that differ only in letter case can fail to match.
- A supplemental data source only updates products whose IDs already exist in a primary data source. It cannot add or remove products. Rows whose IDs are not in a primary source are not applied.
- The ID a supplemental feed needs is the item ID exactly as the primary source sends it, for example `SKU-1234` or `shopify_US_123_456`. A full Merchant Center product ID such as `online:en:US:SKU-1234` is not the item ID; only the last part is.
- **Where IDs come from matters.** The store's feed, a Merchant Center product download, and the Google Ads API's `shopping_product.item_id` all give IDs exactly as Merchant Center holds them. Reports downloaded from the Google Ads interface often show item IDs in lower case, so use those reports for clicks only, never as the source of IDs.

## Supplemental data sources

- A supplemental data source provides extra details, or updates existing details, for products that already come from a primary data source.
- You choose which primary data source(s) it applies to when you create it.
- In the current Merchant Center the "Supplemental sources" tab only shows once the "Advanced data source management" add-on is turned on (Settings, then Add-ons).
- Inputs: a file, a Google Sheets template, or the API.
- Removing the supplemental source removes its overrides; products go back to their primary-source titles once Merchant Center reprocesses them.

## Upload steps (current Merchant Center, checked November 2026)

From Google's "Create a product data source" page. Give users these, with the real file name:

1. Settings (gear icon) → Add-ons → turn on "Advanced data source management". Once per account; without it the "Supplemental sources" tab doesn't appear.
2. Settings → Data sources → "Supplemental sources" tab → "Add supplemental product data".
3. Choose "A file" and follow the prompts. The file name must exactly match the uploaded file, extension included. If asked for a data source (feed) label and language, match the primary data source.
4. Select the primary data source to add the data to, then "Create data source".
5. Allow up to a day for processing, then check the source for errors. Rows whose IDs aren't in the primary source aren't applied.

## File format

- Delimited text files are tab-separated: `.txt` or `.tsv`. XML is the other option. CSV is not listed as a supported upload format, so this skill writes `.tsv`.
- First row: attribute names, one per column. One product per row. Empty cells are allowed.
- Save as UTF-8. No tabs or line breaks inside a value: they break the columns.
- From Google Sheets: File, Download, Tab-separated values (.tsv). From Excel: Save as "Text (tab delimited) (*.txt)".

## Testing new titles first (general guidance, not Google policy)

Uploading the supplemental feed changes the titles of every product in it. Users who want proof first can test on a handful of products:

1. Pick a few top sellers.
2. Duplicate them where products enter Merchant Center (the feed app, store app or primary feed), with new item IDs. A supplemental feed cannot create the duplicates.
3. Change nothing else on the duplicates, links included. The new item ID is what makes Google treat a duplicate as a separate product.
4. Give only the duplicates the new titles (in the duplicate rows themselves, or with supplemental rows keyed to the duplicates' IDs).
5. Run originals and duplicates in the same campaign for 4 to 6 weeks.
6. Compare impressions, clicks, revenue and ROAS for each original against its duplicate, by item ID.
7. Roll the winning titles out to the catalogue, and remove the losing copies.

Whether or not they test, users should look again after 4 to 6 weeks at which searches the products now show for, and rerun the skill every few months as search behaviour and the catalogue change.

## Sources

- Title [title] and structured title [structured_title]: https://support.google.com/merchants/answer/6324415
- AI-generated content: https://support.google.com/merchants/answer/14743464
- ID [id]: https://support.google.com/merchants/answer/6324405
- Item group ID [item_group_id]: https://support.google.com/merchants/answer/6324507
- Create a product data source (primary and supplemental): https://support.google.com/merchants/answer/14990942
- Set up supplemental product data sources (IDs must exist in a primary source): https://support.google.com/merchants/answer/15157604
- Create a product file for Merchant Center (file types, tab-delimited, UTF-8): https://support.google.com/merchants/answer/12631822
