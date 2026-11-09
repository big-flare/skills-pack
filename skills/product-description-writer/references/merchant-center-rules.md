# Google Merchant Center rules this skill follows

Read this before writing the end-of-run instructions, and whenever a user asks why a rule exists. Every rule below comes from Google's own help pages (listed at the bottom, checked November 2026). Google changes these pages; if a user reports a rejection that contradicts this file, trust the live page and tell the user.

## The `description` attribute

- **Length:** 1 to 5,000 characters. Longer text is cut off with a warning.
- **Put the important details first:** Google's best practice is to list the most important details in the first 160 to 500 characters, because shoppers have to click through to read the rest.
- **Describe only the product.** No accessories, compatible or similar products, business history or store policies. Google's page doesn't say whether a product's warranty or trial period counts as a store policy. This skill treats one that the product's own data states ("10-year warranty", "100-night trial") as a fact about the product and keeps it; store-wide shipping, delivery and returns lines stay out.
- **Professional, grammatically correct language.** No all caps, symbols or promotional wording to grab attention. No capital letters for emphasis (abbreviations, phone numbers, countries and currencies are fine).
- **No promotional text:** no price, sale price, sale dates, shipping, delivery dates, other time-related information, or company name. Those belong in their own attributes.
- **No links** to your store or any other website.
- **No comparisons** to other products.
- **No references to categorisation systems** (put those in `google_product_category` or `product_type`).
- **Consistent** with the title and the landing page.
- **Variants:** list the defining details (colour, size, age group, pattern, flavour, material). Each variant gets its own description.
- **Include** relevant features and visual attributes: size, material, intended age range, special features, technical specifications, shape, pattern, texture, design.
- **Language:** most of the product data must be in the data source's language. Foreign words only when well understood.
- **Unicode is accepted; ASCII is recommended.**

## AI-written descriptions: `structured_description`

Google requires descriptions created with generative AI to be declared:

- AI-generated descriptions must be provided with the `structured_description` attribute, with the `digital_source_type` sub-attribute set to `trained_algorithmic_media` and the text in the `content` sub-attribute.
- Google's AI-content page says the structured attribute is used "instead of, or in addition to" the existing description attribute.
- If a product has both `description` and `structured_description`, Google uses `description`.

In a text file the value is the source type, a colon, then the text in double quotes, with any double quote inside the text doubled:

```
trained_algorithmic_media:"The text of the description, with ""quotes"" doubled."
```

**What this skill does about it:** the supplemental feed carries three columns, `id`, `description` and `structured_description`, and both text columns hold the same new text. The `description` column is what overrides the old text (because when both exist, Google uses `description`). The `structured_description` column declares the text as AI-generated, which is what Google's AI-content rule asks for. Sending only `structured_description` would not work: the product's original `description` from the primary feed would still win.

If a user's tool cannot take the third column, a two-column file (`id`, `description`) still overrides the text, but it does not declare the text as AI-generated. Tell the user that plainly and let them decide; never drop the column silently.

## The `id` attribute and matching

- IDs are 1 to 50 characters, case-sensitive, and should never change once assigned.
- A supplemental data source matches products by `id`. The match must be exact. IDs that differ only in letter case can fail to match between supplemental and primary sources.
- A supplemental data source only updates products whose IDs already exist in a primary data source. It cannot add or remove products. Rows whose IDs are not in a primary source are not applied.
- The ID a supplemental feed needs is the item ID (sometimes called offer ID) exactly as the primary source sends it, for example `SKU-1234` or `shopify_US_123_456`. A full Merchant Center REST product ID such as `online:en:US:SKU-1234` is not the item ID; only the last part is.

## Supplemental data sources

- A supplemental data source provides extra details, or updates existing details, for products that already come from a primary data source.
- You choose which primary data source(s) it applies to when you create it.
- In the current Merchant Center the "Supplemental sources" tab only shows once the "Advanced data source management" add-on is turned on (Settings, then Add-ons).
- Inputs: a file, a Google Sheets template, or the API.
- Removing the supplemental source removes its overrides; products go back to their primary-source values once Merchant Center reprocesses them.

## File format

- Delimited text files are tab-separated: `.txt` or `.tsv`. XML is the other option. CSV is not listed as a supported upload format, so this skill writes `.tsv`.
- First row: attribute names, one per column. One product per row. Empty cells are allowed.
- Save as UTF-8 (UTF-16 also works). No tabs or line breaks inside a value: they break the columns.
- Files up to 4 GB.
- From Google Sheets: File, Download, Tab-separated values (.tsv). From Excel: Save as "Text (tab delimited) (*.txt)".

## Product variants

- All variants of one product share one `item_group_id`; each distinct product group has its own value.
- Variants differ by details such as colour, size, material, pattern, age group and gender, and the landing page should match each variant's values.

## A/B testing new descriptions (general guidance, not Google policy)

Feed tools differ, so give users the principle, not button clicks:

1. Pick a handful of top sellers (5 to 10 products is plenty to start).
2. Duplicate them where products enter Merchant Center (the feed app, store app or primary feed), with new item IDs. A supplemental feed cannot create the duplicates.
3. Give each duplicate a distinct landing-page URL parameter (for example `?desc_test=b`) so Merchant Center treats it as a separate item rather than merging it with the original.
4. Give only the duplicates the new descriptions (in the duplicate rows themselves, or with supplemental rows keyed to the duplicates' IDs).
5. Run originals and duplicates in the same campaign for 4 to 6 weeks.
6. Compare impressions, clicks, revenue and ROAS for each original against its duplicate, by item ID.
7. Keep the winner: roll the winning descriptions out to the catalogue, and remove the losing copies.

## Sources

- Description [description] and structured description [structured_description]: https://support.google.com/merchants/answer/6324468
- AI-generated content: https://support.google.com/merchants/answer/14743464
- ID [id]: https://support.google.com/merchants/answer/6324405
- Item group ID [item_group_id]: https://support.google.com/merchants/answer/6324507
- Create a product data source (primary and supplemental): https://support.google.com/merchants/answer/14990942
- Set up supplemental product data sources (IDs must exist in a primary source): https://support.google.com/merchants/answer/15157604
- Create a product file for Merchant Center (file types, tab-delimited, UTF-8): https://support.google.com/merchants/answer/12631822
