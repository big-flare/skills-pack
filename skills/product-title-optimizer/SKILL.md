---
name: product-title-optimizer
description: Rewrites Google Shopping product titles around what shoppers actually search, using the store's own Google Ads search terms (pulled through a Google Ads connection or from an uploaded report), Keyword Planner and the store's website, then outputs a supplemental feed you upload to Google Merchant Center to replace the titles in Shopping without touching your store or main feed. Also produces an editable review workbook and a before/after review page. USE WHEN you want better Google Shopping titles, your titles are short or written for browsing rather than searching, variants share one title, or you want a supplemental feed of new titles. NOT for product descriptions, website or product-page copy, ad copy, or fixing feed errors other than titles.
version: 2.0.0
pack: big-flare-skills-pack
---

# Product Title Optimizer

Rewrite each product's Google Shopping title so it carries the words people search, and deliver the new titles as a supplemental feed the user uploads to Google Merchant Center.

Why this works: in Google Shopping there are no keywords to bid on, so the title decides which searches a product shows for. Most titles are written for people browsing a website and use 40 to 60 of the 150 characters Google allows. A title built from the store's own search terms, with the most-searched phrase first and every character earning its place, can show for far more of the searches that matter. The skill never changes the user's store, feed or Google accounts: the user uploads the file themselves.

## How the run works

1. Products and the settings. 2. The search data question (always asked). 3. Load the data. 4. Research each category. 5. Write titles in batches. 6. Check. 7. Build the outputs. 8. Deliver, then apply the user's edits.

Files the run creates, in one folder named `<store>-titles/` in the user's working directory:

| File | What it is |
|---|---|
| `run-config.json` | The run's settings: feed, ID column, language, store, brand rule |
| `products.jsonl` | The chosen products in one record shape (from any input path) |
| `terms.jsonl`, `planner.jsonl` | Search terms and Keyword Planner ideas, when used |
| `research.json` | Research notes per category |
| `drafts.jsonl` | One saved title per product, written batch by batch |
| `check-report.json` | Errors and warnings from the last check |
| `<store>-supplemental-titles.tsv` | **Output 1:** the supplemental feed for Merchant Center |
| `<store>-title-review.xlsx` | **Output 2:** the review workbook: titles to edit, research, keywords |
| `<store>-title-review.html` | **Output 3:** the review page (before/after, what to check, next steps) |

**Resuming:** if the folder already exists, do not start again. Run `next` (or read `drafts.jsonl` by hand) and carry on from the first product without a title.

**The helper script.** Check once whether Python runs (`python3 --version`, or `python --version` on Windows). If it does, use `scripts/titletool.py` for every mechanical step: it needs nothing installed, parses feeds and Google Ads reports, counts characters exactly, matches search terms to products, enforces the rules in the check, and writes all three outputs. If Python is not available, do the same steps by hand following the same rules (each step says how), and count every title's characters with whatever code tool you have; never by eye. In the commands below, `<skill-dir>` is the folder this SKILL.md is in; run them from the user's working directory so the run folder lands there. `references/data-sources.md` has the queries and download steps for every data path.

## Step 1 — Products and the settings

**Getting the products.** The best source is the feed Merchant Center reads (or a Merchant Center product download): it has the exact item IDs plus the brand, product type, variant attributes and links. With a Google Ads connection, the account's product list is another source (query in `references/data-sources.md`); it also gives each product's clicks. Accept Google Shopping XML, `.tsv`/`.txt`/`.csv`, `.xlsx`, a feed URL you can download with code, or a short paste for a test. A store's own product export (for example a Shopify product CSV) usually lacks the IDs Merchant Center uses; the inspect step warns about it. If the user hasn't given products yet, ask for them in the same message as the Gate (Step 2), so there is only one round trip.

```
python3 <skill-dir>/scripts/titletool.py inspect <feed-file> --store "<Store name>" [--perf <clicks-report>]
```

It reports the item ID column, variant groups, brands, categories, what is wrong with the current titles, the language, and, when clicks are known, how much of the store's clicks the top 25, 50, 100 and 250 products account for. By hand: read the header row and 20 to 30 rows and note the same things.

**Worked out from the data, not asked.** State these in one line in your first message, so a wrong reading gets caught, and don't ask the user to confirm them:

- **The item ID column:** the feed's `id` (`g:id`, item ID, offer ID). It must be exact: Merchant Center matches supplemental rows by exact, case-sensitive ID and silently skips the rest. Stop and tell the user, rather than guessing, if there is no ID column or the IDs show scientific notation (`1.23E+13`).
- **Language and spelling:** the feed's language and market spelling (colour or color). Titles are written in it.
- **The brand rule:** whether the store sells its own brand (that name ends every title) or resells other brands (each product's brand goes in the first half; the store's name is left out, per Google's rules). See `references/title-guide.md`, Brand.

For example: "I'll match on the `id` column (e.g. SKU-1001), write in English with UK spelling (prices are in GBP), and end each title with your brand, Loma Studio."

**Which products.** Skip the question when the user has already said ("all of them", "the top 50", a list), or the feed has 50 products or fewer: do them all and say so. Otherwise ask, recommending the products that get the most clicks, because that is where better titles pay back fastest and the user has to read every title before uploading:

- **Clicks known** (Google Ads connected, or a clicks report): offer the top 50, 100 or 250 with their share of clicks from `inspect` ("your top 50 products get 71% of your Shopping clicks"), or all of them.
- **Clicks not known:** ask the user to name their best sellers (IDs, titles or product URLs), or choose the first N rows, a category, or the whole feed.

Settled means the user named products or chose an option. "Whatever you think" is not an answer when clicks are unknown: ask once more, explaining that the feed doesn't show which products sell.

## Step 2 — Gate: the search data route. Ask this every run.

**This question is mandatory. Ask it every run, before loading anything else, and do not proceed until it is resolved.** The store's own search terms are the strongest evidence a title can be built on: they are the exact words shoppers typed before they saw the products. Titles built without them rest on judgement alone. Skipping this question silently is the most damaging mistake this skill can make.

Offer only the routes that exist in this session, numbered from 1 in the order below (with no Google Ads connection, the report becomes option 1 and going without becomes option 2):

> "One more thing before I start. The best titles are built from your real search terms: the exact searches that showed your products in Google. I can **(1)** pull them from your Google Ads account now [offer only if a Google Ads connection is available in this session], **(2)** use a search terms report you download from Google Ads (I'll tell you where; a Keyword Planner export helps too if you have one), or **(3)** go without, using your product pages and my judgement, which gives noticeably weaker titles. Which would you like?"

**Resolved means** the user picked a route, or already supplied search term data, or explicitly said to go without. Silence, "go ahead" or "whatever works" is not a choice: ask once more and repeat what option 3 costs. If the user picks option 2, give them the download steps from `references/data-sources.md` and wait for the file.

Ask the Gate in the same message as the products question when both are open, so the user answers everything at once.

## Step 3 — Load the data

Normalise the chosen products:

```
python3 <skill-dir>/scripts/titletool.py normalise <feed-file> --run <store>-titles --store "<Store name>" \
    (--top 50 | --pick-file picks.txt | --first N | --all) [--perf <clicks-report>]
```

`picks.txt` holds one item ID, product URL or product title per line, as the user gave them. Every variant of a chosen product is included automatically, because a variant group shares one title template. Add `--id-col`, `--lang`, `--brand-case own|reseller`, `--end-brand "<Name>"` or `--no-end-brand` only when the user said so. It prints the brand rule (including any brand values it ignored as internal labels, such as season codes or sale tags), the categories, and the share of clicks the chosen products cover. It also lists **unmatched picks** (nothing found) and **ambiguous picks** (one name matched several products, which are all included for now). Show both to the user, settle them with item IDs or product URLs, and rerun `normalise` with `--force` and the corrected picks before writing; titles already saved are kept. By hand: create `products.jsonl` with the fields `id`, `item_group_id`, `title`, `brand`, `product_type`, `category`, `attributes`, `link`, `variant_parts`, `group`, `group_size` (and `clicks` when known), so every path ends in the same record shape.

Then load the search data from the route the user chose. Pulled through a connection? Save the query results as a CSV first (`references/data-sources.md` has the queries), then load the file exactly as if the user had uploaded it:

```
python3 <skill-dir>/scripts/titletool.py terms <search-terms-file> --run <store>-titles
python3 <skill-dir>/scripts/titletool.py planner <keyword-planner-file> --run <store>-titles [--category "<category>"]
```

`terms` can be run more than once (for example Search plus Performance Max); it merges. If a pull fails or comes back empty, tell the user and offer the manual route or going without. Never invent search terms or search volumes.

## Step 4 — Research each category

Research by category, not product by product: a store with 500 products in 12 categories needs about 13 page reads, not 500.

```
python3 <skill-dir>/scripts/titletool.py categories --run <store>-titles
```

For each category it lists the top products, the page to read, and the best-matching search terms and Keyword Planner ideas. Then:

1. Read the store's homepage once, then the listed product page for each category. When a category mixes different kinds of product, read one page per kind instead; if the listed page is out of stock or thin, read another (`references/data-sources.md` has the Shopify `.json` shortcut and the web-search fallback for blocked pages).
2. Note for each category: what the products are, who they're for, the benefits the store leads with, how the store positions them, and the search phrases worth targeting from every source.
3. Look at `unmatched_search_terms`: searches with real volume that share no product word with any category. Some name a product in other words (a "travel backpack" search for a daypack, "carry on luggage" for a suitcase). Note those against the category they fit; they are often the biggest opportunities in the run, because the current titles don't contain them. Ignore the rest.
4. With a Keyword Planner connection and no planner data yet, request ideas once per category now and load them with `planner --category`.
5. Save the notes. They feed the workbook's Research tab, which the user reads:

```
python3 <skill-dir>/scripts/titletool.py research --run <store>-titles notes.json
```

`notes.json` is a list of `{"category", "summary", "audience", "benefits": [...], "positioning", "pages": [urls]}`. Fill every field from what you actually read; if a page couldn't be read, say so in `summary` rather than filling the gap from general knowledge.

## Step 5 — Write titles, in batches

Read `references/title-guide.md` in full before the first batch. It holds the title structure, the brand and variant rules, the keyword priorities, worked examples and the self-check.

```
python3 <skill-dir>/scripts/titletool.py next --run <store>-titles --batch 20
```

A batch can run a few products over 20, because a product's variants always stay together. Each product comes with its best-matching search terms (with impressions and clicks), and each category with its Keyword Planner ideas and research notes. The matching is word overlap, so judge relevance yourself: use a search term only if it describes this product, and add any unmatched search term you noted in Step 4 where it fits. Write each title, self-check it, record the phrases it targets with their sources, then save the batch straight away:

```
python3 <skill-dir>/scripts/titletool.py add --run <store>-titles batch.json
```

`add` prints every title's exact length: fix anything outside 130 to 150 before moving on. If `add` reports a problem (an unknown ID, a missing field), nothing in that batch is saved: fix the batch file and run `add` again. Saving after every batch is what makes a long run resumable. By hand: append each draft as one JSON line to `drafts.jsonl` after every batch. Work sequentially; parallel workers are optional where available and must follow the same guide.

Give the user a one-line progress note between batches on long runs ("60 of 150 done").

## Step 6 — Check

```
python3 <skill-dir>/scripts/titletool.py check --run <store>-titles
```

Errors must be fixed: rewrite the title and `add` it again (a new draft for the same ID replaces the old one). Errors include: over 150 characters, the brand not last (own brand) or not in the first half (resold brand), a variant value missing, a number that isn't in the product's data, promotional, price, shipping or time-related text, exclamation marks, empty sections, and duplicate titles. Warnings need a look and either a fix or a reason, written in that title's `notes` (they show in the workbook and on the review page): under 130 characters, sections that repeat each other, capitals for emphasis, "best" or price words that nobody searches, health wording, spelling for the market, and titles that dropped most of the original's words.

By hand: go through the same list for every title, using the self-check at the end of the title guide.

## Step 7 — Build the outputs

```
python3 <skill-dir>/scripts/titletool.py build --run <store>-titles
```

It refuses to build while errors remain (`--force` builds anyway and holds the products with errors back from the feed file).

- **Output 1, the supplemental feed** (`.tsv`, UTF-8, tab-separated): columns `id`, `title`, `structured_title`. Both text columns hold the same new title; `structured_title` is written as `trained_algorithmic_media:"<title>"` with inner double quotes doubled. Google requires AI-written titles to be declared through `structured_title`, and when a product has both, Google uses `title`, so the pair both replaces the old title and declares it. Details: `references/merchant-center-rules.md`.
- **Output 2, the review workbook** (`.xlsx`): a **Titles** tab (ID, original title, new title, a live character count that turns red outside 130 to 150, keywords targeted, clicks when known, notes), a **Research** tab (the category notes) and a **Keywords** tab (every targeted phrase with its source, search volume and search-term clicks). IDs are stored as text so spreadsheets can't mangle them.
- **Output 3, the review page** (`.html`), built from `references/review-template.html`: brand header, a stat row, up to three visuals (what was wrong with the original titles, length before and after, where the keywords came from), "Check these first", "Before and after" for every product, and "What to do next". Keep the brand header and footer credit intact. Visuals come only from real counts; when there is nothing to show, the visual is dropped, never filled with made-up numbers. To re-brand, change only the `:root` token values.

By hand (no Python): write the `.tsv` yourself with a header row and one tab-separated row per ready title; for the review, a CSV with the Titles tab's columns does the job of the workbook (tell the user to keep the ID column as text if they open it in a spreadsheet); for the page, copy the template file and fill the placeholders and the content marker using the component markup in its closing comment. Never retype the brand header: copy the file.

## Step 8 — Deliver, then apply the user's edits

Give the user:

1. The three files, with their paths.
2. Three to five lines on what you found: how many titles were written, average length before and after, how many of their real search terms are now in the titles (or that no search data was used), and the biggest problem with the originals.
3. A before/after preview of the top 10 products in the chat.
4. Anything to check (warnings, held products), or "nothing to check".
5. Next steps:
   - **Review and edit** in the workbook's Titles tab, then send the saved file back and say "apply my edits".
   - **Upload, step by step**, with the file's real name filled in (the same steps are on the review page):
     1. Settings (gear icon) → Add-ons → turn on "Advanced data source management". Once only; without it the Supplemental sources tab doesn't show.
     2. Settings → Data sources → "Supplemental sources" tab → "Add supplemental product data".
     3. "A file": the file's exact name, extension included, then upload the file. If asked for a feed label and language, use the main feed's.
     4. Pick the primary data source the products come from → "Create data source".
     5. Allow up to a day, then check the source processed without errors. Rows whose `id` matches no product are ignored.
     Deleting the source brings the original titles back. The menu names come from Google's help (checked November 2026); if the user says a menu has moved, point them to Merchant Center Help for "supplemental data source" rather than guessing a new path.
   - **Optional test first:** duplicate a few top sellers with new item IDs and nothing else changed (the links stay the same), give only the duplicates the new titles, run both in the same campaign for 4 to 6 weeks, compare by item ID and keep the winner.

**When the user sends the edited workbook back:**

```
python3 <skill-dir>/scripts/titletool.py apply <edited-file> --run <store>-titles
```

It reads the Titles tab, saves every changed title as the user's edit (dropping any recorded keyword the new wording no longer contains), re-checks everything (an edit can push a title over 150 characters or drop a variant), and rebuilds all three outputs. Its `checks_on_edited_titles` lists the errors and warnings on the titles the user changed. Report what changed and any new errors, and fix errors with the user rather than overriding their wording silently. A title the user cleared is held back from the feed. The feed file is what gets uploaded, so always rebuild it after edits; never hand over a feed that predates the user's changes.

Offer natural next steps: the next batch of products, a rerun with search data if this run went without, or titles for test duplicates' IDs.

## Hard rules

- **Ask the search data question every run** (Step 2), and never present your own keyword ideas as search data. Every phrase's recorded source is its true source.
- **150 characters is a hard limit.** Count with code, never by eye, and check the final title, including after the user's edits.
- **Own brand last; a resold brand in the first half.** Don't add the store's own name to a reseller's titles unless the user asks for it.
- **Every variant's distinguishing values stay in its title, copied exactly.** Never guess, swap or invent a variant.
- **Numbers come only from the product's data.** No invented sizes, counts or specs.
- **Nothing promotional:** no prices, sales, shipping, dates, exclamation marks, capitals for emphasis, or "best"-type words that nobody searches.
- **IDs are copied exactly** from the feed. Never edit, trim or re-case an ID, apart from cutting a full Merchant Center product ID (`online:en:US:ABC123`) down to its item ID.
- **Nothing is uploaded or changed in the user's store, feed, Google Ads or Merchant Center by this skill.** Google Ads connections are used to read data only. The user uploads the file themselves.
