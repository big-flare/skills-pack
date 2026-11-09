---
name: product-description-writer
description: Rewrites Google Shopping product descriptions from each product's own feed data, giving every product and every variant its own clear, fact-only description, then outputs a supplemental feed you upload to Google Merchant Center to replace the descriptions in Shopping without touching your store or main feed. Also produces a before/after review page that flags every fact the sources disagree on, plus a simple A/B test plan. USE WHEN you want better Google Shopping descriptions, your feed descriptions are stripped bullet lists, shared across sizes or colours, thin or missing, or you want a supplemental feed of new descriptions. NOT for product titles, website or product-page copy, ad copy, or fixing feed errors other than descriptions.
version: 1.0.1
pack: big-flare-skills-pack
---

# Product Description Writer

Write a new Google Shopping description for each product in a feed, using only that product's own data, and deliver it as a supplemental feed the user uploads to Google Merchant Center.

Why this works: many feed descriptions are a product page's bullet list with the HTML stripped out, which turns into one run-on block with no full stops, and one text is often shared by every size and colour of a product. Descriptions that name the exact product and variant, read as four or five real sentences, and carry every fact from the product's own data give Google and shoppers more to work with. The skill never invents anything: no facts, numbers, benefits or claims that the product's data does not contain.

## How the run works

1. Get the feed. 2. Inspect it. 3. Settings, and one question (which products). 4. Optional: read product pages. 5. Write in batches, saving as you go. 6. Check. 7. Build the outputs. 8. Deliver with next steps.

Files the run creates, in one folder named `<store>-descriptions/` in the user's working directory:

| File | What it is |
|---|---|
| `run-config.json` | The run's settings: feed, ID column, language, store name |
| `products.jsonl` | The chosen products in one record shape (from any input path) |
| `drafts.jsonl` | One saved draft per product, written batch by batch |
| `check-report.json` | Errors and warnings from the last check |
| `<store>-supplemental-descriptions.tsv` | **Output 1:** the supplemental feed for Merchant Center |
| `<store>-description-review.html` | **Output 2:** the review page (before/after and flagged conflicts) |

**Resuming:** if the folder already exists, do not start again. Run `next` (or read `drafts.jsonl` by hand) and carry on from the first product without a draft.

**The helper script.** Check once whether Python runs (`python3 --version`, or `python --version` on Windows). If it does, use `scripts/feedtool.py` for every mechanical step: it needs nothing installed, parses the feed formats, keeps the record shape consistent, enforces the rules in the check, and splices the review page from the template. If Python is not available, do the same steps by hand following the same rules (each step says how). The script makes the run faster and more reliable; it is not required. In the commands below, `<skill-dir>` is the folder this SKILL.md is in; run the commands from the user's working directory so the run folder lands there.

## Step 1 — Get the feed

The floor input is a feed file the user uploads or pastes. Accept any of:

- **Google Shopping XML** (RSS 2.0 or Atom with `g:` tags), as served by most feed apps.
- **Delimited text**: `.tsv`, `.txt`, `.csv` (tab, comma, semicolon or pipe).
- **A spreadsheet**: `.xlsx` (first sheet), or a Google Sheets feed downloaded as `.tsv`/`.csv`.
- **A Merchant Center product download.** Its IDs are guaranteed to be the ones Merchant Center uses, which matters most of all.
- A short paste of rows, for a quick test.

The best file is whatever feeds Merchant Center today (the feed app's feed, or the primary data source's file), because it has the richest attributes (product highlights, product details, colour, size, material) and the exact item IDs. A store's own product export (for example a Shopify product CSV) usually does **not** contain the IDs Merchant Center uses; the inspect step warns about this, and a supplemental feed built from it will not match.

Other paths, all optional:

- **A feed URL.** If you can download it with code that has internet access, do; otherwise ask the user to download the file and upload it. Never rely on a web-page fetch tool to read a large feed: it may summarise or truncate it.
- **A connected integration** (a Merchant Center, Shopify or feed-tool connection) if one happens to be available in this session: use it to pull the same fields, then save them as a feed file and continue from Step 2 exactly as if the user had uploaded it. Never required, never assumed.

If the user has not given a feed, ask for it, and in the same message ask which products to start with (Step 3), so the run does not need an extra round trip.

## Step 2 — Inspect the feed

```
python3 <skill-dir>/scripts/feedtool.py inspect <feed-file>
```

It reports the columns, the item ID column it will use (or why the file can't be used), variant groups, what is wrong with the current descriptions (shared, run-on, HTML, promotional text, empty), whether product links exist, and the language and spelling it will write in, with the evidence. By hand: read the header row and 20 to 30 rows and note the same things.

Use this to settle Step 3. Do not start writing.

## Step 3 — Settings, and one question

The run works out two settings from the feed and asks the user one question, which products to do. **Do not normalise products or write anything until the products are settled.**

**Worked out from the feed, not asked:**

- **The item ID column.** Use the feed's standard ID column: `id` (`g:id` in XML, `item id` or `offer id` in some downloads). This is the one thing that must be exact, because Merchant Center matches supplemental rows to products by exact, case-sensitive ID and silently skips rows that don't match. If the IDs are full Merchant Center product IDs (`online:en:US:ABC123`), only the last part is the item ID, and the script strips the rest. Stop and tell the user, rather than guessing another column, in two cases: the file has no ID column (usually a store export, not the feed Merchant Center reads; ask for the feed itself), or the IDs show scientific notation (`1.23E+13`, a spreadsheet mangled them; ask for a re-export with the ID column as text). If the user names an ID column, use theirs.
- **Language and spelling.** Write in the feed's language, with its market's spelling (colour or color, grey or gray, aluminium or aluminum). The inspect step decides this from the feed: a language or target-country column, the price currency, the link domains (.co.uk, .com.au) and the spelling of the current copy. If it can't tell the spelling market, use the store's website: when you read the first product page, check its language tag (such as `lang="en-GB"`) or its own spelling. If there is still no signal, use US spelling. If the user states a language or spelling, use theirs.

State both in one line in your first message, so a wrong reading gets caught, for example: "I'll match on the `id` column (e.g. SKU-1001) and write in English with UK spelling (prices are in GBP and the links are on .co.uk)." Don't ask the user to confirm them.

**The one question: which products first.** Skip it when the user has already said which products ("all of them", "the first 50", a list of products), or when the whole feed is 50 products or fewer: do the whole feed and say so. Above 50 products, always ask, even when the feed is only a little over: how much of the catalogue to do is the user's call, not yours. When you ask, recommend a test batch of the store's top sellers (10 to 25 products) rather than the whole catalogue. Three reasons: the user has to read the output before uploading, which is realistic for 20 products and not for 2,000; a full catalogue takes hours and a lot of usage; and the top sellers are where better descriptions pay back fastest and where an A/B test collects data quickest. The feed doesn't show sales, so the user must name them: item IDs, product titles or product URLs, pasted or as a file. Every variant of a named product is included automatically (each variant gets its own description). They can also choose a filter ("all the jackets"), the first N rows, or the whole feed. Suggested phrasing: "Which products should I do first? I'd start with 10–25 of your best sellers: you can read every description before uploading, and it's where better descriptions pay back fastest. The feed doesn't tell me what sells, so paste the IDs, titles or product URLs. Or I can do the first N rows, or the whole feed." Settled means the user named products or explicitly chose a filter, first N or the whole feed. "Go ahead" or "whatever you think" without naming products is not an answer: ask once more, explaining that the feed can't tell you which products sell.

In the same message (or in your first progress line, when there was no question to ask), mention two optional settings and what you'll do by default:

- **Reading product pages for extra facts** (on by default when the feed has product links and the batch is 50 products or fewer; off otherwise). Pages add facts and, more importantly, reveal where the page and the feed disagree.
- **Anything the user wants avoided or always included** (a brand style, words they never use). Only facts from the data still go in.

Then normalise the chosen products:

```
python3 <skill-dir>/scripts/feedtool.py normalise <feed-file> --run <store>-descriptions \
    --pick-file picks.txt --store "<Store name>"
```

(`--pick` for a few items on the command line, `--first N`, or `--all`. Add `--id-col <column>` or `--lang <code>`, such as `en-GB`, only when the user named one.) It prints the ID column and language it used, and any unmatched or ambiguous picks: show those to the user and resolve them before writing. By hand: create `products.jsonl` yourself with the same fields (`id`, `item_group_id`, `title`, `description_original` as plain text, `highlights`, `details`, `product_type`, `brand`, `attributes`, `link`, `variant_parts`) so every input path ends in the same record shape.

## Step 4 — Optional: read product pages

Skip this step if the user turned it off or the products have no links. Otherwise, for each item group (variants share a page, so read it once per group):

- Fetch the product page. On Shopify stores, adding `.json` to a product URL (`/products/<handle>.json`, with any `?variant=` part removed) usually returns the same product data as clean JSON; use it when it works.
- Take **product facts only**: materials, dimensions, capacity, features, care. Ignore reviews, shipping and returns, promotions, related products and anything generic to the store.
- Compare each page fact with the feed's facts. Different values for the same fact are a **conflict** (see the writing guide).
- If a page fails to load or blocks fetching, record `"page": {"status": "failed"}` and carry on with the feed data. Never stop the run for it, and never fill the gap from general knowledge.

## Step 5 — Write, in batches

Read `references/writing-guide.md` in full before the first batch. It holds the recipe, the fact-sheet method, the variant and conflict rules, the leave-out list, and a worked example.

Work in batches of about 10 products, keeping a product's variants in the same batch:

```
python3 <skill-dir>/scripts/feedtool.py next --run <store>-descriptions --batch 10
```

For each product: build the fact sheet, note conflicts and items to leave out, write the description, self-check it, and add the draft record to a batch file. Then save the batch straight away:

```
python3 <skill-dir>/scripts/feedtool.py add --run <store>-descriptions batch.json
```

Saving after every batch is what makes a long run resumable. By hand: append each draft as one JSON line to `drafts.jsonl` after every batch. Sequential work is the default; if your environment offers parallel workers, they are optional and each must follow the same writing guide.

Tell the user briefly how far you have got between batches on long runs ("40 of 120 done, 3 conflicts so far").

## Step 6 — Check

```
python3 <skill-dir>/scripts/feedtool.py check --run <store>-descriptions
```

Errors must be fixed: rewrite the draft and `add` it again (a new draft for the same ID replaces the old one). Errors include a number that is not in the product's data, an unnamed variant, prices, shipping or promotional wording, links, exclamation marks, identical descriptions, and anything over 5,000 characters. Warnings need a look and either a fix or a reason: length outside 500–900, health wording, superlatives not in the data, US/UK spelling slips, a conflicting fact that leaked into the copy, and originals whose words mostly disappeared (a sign a fact was dropped).

By hand: go through the same list for every draft, using the self-check at the end of the writing guide.

## Step 7 — Build the outputs

```
python3 <skill-dir>/scripts/feedtool.py build --run <store>-descriptions
```

It refuses to build while errors remain (`--force` builds anyway and holds the products with errors back from the feed file).

**Output 1, the supplemental feed** (`.tsv`, UTF-8, tab-separated): columns `id`, `description`, `structured_description`. Both text columns hold the same new text; `structured_description` is written as `trained_algorithmic_media:"<text>"` with inner double quotes doubled. Google's rules require AI-written descriptions to be declared through `structured_description`, and when a product has both attributes Google uses `description`, so the pair both replaces the old text and declares it. Details and sources: `references/merchant-center-rules.md`. Held products are not in the file.

**Output 2, the review page** (`.html`), built from `references/review-template.html`: brand header, a stat row, up to three data visuals (what was wrong with the originals, length before and after, flags for review), then "Decisions for you" (every conflict, with what each source says, and any held products), "Before and after" for every product, and "What to do next". Keep the brand header and the footer credit intact. Visuals come only from real counts; when there is nothing to show (no flags), the visual is dropped, never filled with made-up numbers. To re-brand, change only the `:root` token values.

By hand (no Python): write the `.tsv` yourself with a header row and one tab-separated row per ready product, following the rules above; for the page, copy the template file and fill the placeholders and the content marker using the component markup in its closing comment. Never retype the brand header: copy the file.

## Step 8 — Deliver

Give the user:

1. The two files, with their paths.
2. Three to five lines on what you found: how many descriptions were written, how many variants now have their own text, the biggest problem with the originals, and how many facts need a decision.
3. The decisions list (or "none").
4. Short next steps, kept general because feed tools differ (full version in `references/merchant-center-rules.md`):
   - **Upload:** in Google Merchant Center, add a supplemental product data source (upload the `.tsv`, or paste it into a Google Sheet and connect the sheet) and link it to the primary data source the products come from. In the current Merchant Center the supplemental sources tab appears once the "Advanced data source management" add-on is on. Check the source's processing report after the first upload: any ID that doesn't match shows up there. Removing the source brings the original descriptions back.
   - **A/B test before rolling out:** duplicate a handful of top sellers with new item IDs where your products enter Merchant Center (a supplemental feed can't create them), change nothing else on them (the links stay the same), give only the duplicates the new descriptions, run both in the same campaign for 4–6 weeks, then compare impressions, clicks, revenue and ROAS by item ID and keep the winner.

Offer natural next steps: resolve the conflicts and rerun the affected products, do the next batch of products, or write descriptions for the A/B-test duplicates' IDs.

## Hard rules

- **Facts come only from the product's own data** (feed fields, and product-page facts when that path is on). No invented facts, numbers, benefits, uses or claims.
- **Sources disagree? Leave the fact out** and flag it for a human. Never pick a side.
- **No health or medical claims, no superlatives the data doesn't contain, no prices, promotions, shipping, delivery or returns policies, links or comparisons.** A warranty, guarantee or trial period that the product's own data states is a fact about the product, and it stays.
- **Every variant gets its own description that names it.**
- **IDs are copied exactly** from the feed's ID column. Never edit, trim or re-case an ID, apart from cutting a full Merchant Center product ID (`online:en:US:ABC123`) down to its item ID.
- **Nothing is uploaded or changed in the user's store, feed or Merchant Center by this skill.** The user uploads the file themselves.
