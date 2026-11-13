---
name: google-ads-audit-analysis
description: Builds a detailed Google Ads audit workbook for an ecommerce account that opens in Google Sheets. It covers monthly account performance with gross profit after ad spend, where Performance Max and Shopping spend really goes (Shopping ads, Search, YouTube, Display, Gmail, Discover), campaign and asset performance, every product sorted into Profitable, Costly, Low spend and Zombies, product families, market demand from Keyword Planner, and the converting Performance Max searches that have no working Search keyword. The data comes from a Google Ads connection or from a read-only Google Ads Script the user runs. USE WHEN you want to audit a Google Ads account, see where Performance Max spend goes, find which products make or lose money, find keyword gaps, or work out whether a sales drop came from the account or the market. NOT for writing ads or product titles, making changes in Google Ads, or non-Google ad platforms.
version: 1.0.0
pack: big-flare-skills-pack
---

# Google Ads Audit Analysis

Build the analysis behind a Google Ads audit: one workbook that shows where an ecommerce account's money goes and where the opportunities are. The user opens it in Google Sheets, where every dropdown, threshold and chart works.

What the workbook shows, tab by tab:

| Tab | What it answers |
|---|---|
| Start Here | The headline numbers and a guide to the tabs |
| Account | Every month of last year and this year, all campaign types: conversions, cost, conv. value, ROAS, search impression share and lost share, and gross profit after ad spend (from an editable gross margin) |
| Search Volume | Is the market shrinking or the account? Monthly Google searches for the store's main keywords next to the impressions the account was eligible for (optional: needs Keyword Planner data) |
| Channel Split | Where Performance Max and Shopping spend really goes: Shopping ads, Google Search, YouTube, Display, Gmail, Discover. A filter switches between PMax + Shopping, PMax only and the whole account |
| Campaign | The same channel split and daily trends for any one campaign |
| Assets | Performance Max headlines, long headlines, descriptions, images and videos |
| Products | Every product listed today in four buckets: Profitable, Costly, Low spend and Zombies (no spend), with editable thresholds and margin, profit and POAS |
| Product Families | The same buckets for whole products, with sizes and colours grouped, plus a Product Mapping tab |
| Keyword Gap | Performance Max search terms that converted but have no working Search keyword: the keywords to add or fix |

The skill never changes the user's Google Ads account. Connections are used to read data only, and the bundled Google Ads Script only reads.

## How the run works

1. Gate: the date range. 2. Gate: where the data comes from. 3. Get the data. 4. The settings. 5. Search Volume (optional). 6. Product families. 7. Build. 8. Deliver and explain.

Files the run creates, in one folder named `<store>-audit/` in the user's working directory:

| File | What it is |
|---|---|
| `data.json` | The account's data in one shape, from any route |
| `product-families.csv` | Which product IDs make up each product family (editable) |
| `search-volume.json` | Keyword Planner monthly volumes, when used |
| `<store>-google-ads-audit.xlsx` | **The workbook.** Opens in Google Sheets or Excel |
| `summary.json` | The headline numbers, for the chat summary |

**The helper script.** Check once whether Python runs (`python3 --version`, or `python --version` on Windows). The workbook is built by `scripts/audittool.py` (plain Python 3.8 or later, nothing to install). In the commands below, `<skill-dir>` is the folder this SKILL.md is in; run them from the user's working directory. If Python isn't available at all, say that the workbook needs it, and offer what can be done without it: read the data the user provides and give the headline findings in the chat.

## Step 1 — Gate: the date range. Ask this every run.

Every query uses the date range, so settle it before anything else. Recommend the last 90 days, offer year to date, and accept any range the user names:

> "Which dates should the audit cover? I'd suggest the **last 90 days**, or **year to date** if you want the full year's picture, or give me any start and end date."

Resolved means the user picked an option or gave dates. Convert it to two dates (YYYY-MM-DD). The end date is yesterday unless they said otherwise: today is incomplete. The Account and Search Volume tabs always cover 1 January last year to the end date, whatever the range.

## Step 2 — Gate: where the data comes from. Ask this every run.

**Ask it every run and do not go on until it is resolved.** Offer only the routes that exist in this session, numbered from 1 in this order:

> "Where should the data come from? **(1)** I can pull it from your Google Ads account now [only if a Google Ads connection that runs GAQL queries is available in this session], **(2)** you run a read-only Google Ads Script I'll give you: it takes about 2 minutes and saves one file to your Google Drive that you send me, or **(3)** I build it from demo data so you can see what the report looks like first."

Ask in the same message as Step 1 when both are open. Resolved means the user picked a route or has already sent a data file. "Whatever works" is not a choice: recommend the connection if there is one, otherwise the script, and ask again. A large account (hundreds of products or campaigns, or a year or more of data) is often more reliable through the script, because a connection can return results too big to handle.

If the connection can see several accounts, ask which one. Never guess an account.

## Step 3 — Get the data

**Route 1, a Google Ads connection.** Run every query in `references/queries.md` with the dates from Step 1, plus the `account_info` query, and save each result as `<run>/raw/<query name>.json`, complete. If a result is too large to show, use the file the connection saved instead; never copy rows out by hand. Then:

```
python3 <skill-dir>/scripts/audittool.py load <store>-audit/raw --run <store>-audit --from <start> --to <end>
```

**Route 2, the Google Ads Script.** Write the script with the dates filled in:

```
python3 <skill-dir>/scripts/audittool.py script --from <start> --to <end> [--customer-id 123-456-7890] --out google-ads-audit-export.js
```

Add `--customer-id` only when the user will run it from a manager (MCC) account. Give the user the file and these steps:

1. In Google Ads: Tools > Bulk actions > Scripts > the **+** button > New script.
2. Delete the sample code, paste the whole file in, and give the script a name.
3. Click **Authorize** and allow access. The script reads reports and creates one file in their Google Drive. It changes nothing in the account.
4. Click **Run**. When it finishes, open the **Logs**: the last line links to the saved file. Download it and send it here.

If the user says a menu has moved, point them to Google's help for "Google Ads scripts" rather than guessing a new path. When the file arrives:

```
python3 <skill-dir>/scripts/audittool.py load <file> --run <store>-audit
```

**Route 3, demo data.** `load <skill-dir>/examples/demo-data.json --run loma-audit`, then `planner <skill-dir>/examples/demo-keyword-planner.csv --run loma-audit --market "United Kingdom"`. Say plainly that every number is made up.

`load` prints the rows per query, any query that is missing or failed, and which tab that affects. Report missing pieces to the user. Only `campaigns_daily` is essential. Never invent data to fill a gap: a tab without its data is left out.

## Step 4 — The settings

Ask once, in one message, and use the defaults if the user doesn't know or doesn't mind. Every one of them is an editable cell in the workbook, so they can be changed later:

- **Gross margin** (default 50%): the average share of revenue left after product costs. It drives gross profit after ad spend on the Account tab and Profit and POAS on the product tabs. Break-even ROAS is 1 ÷ margin (2.0 at 50%).
- **ROAS threshold** (default 400%) and **cost threshold** (default 50 in the account's currency): a product with at least the cost threshold is Profitable at or above the ROAS threshold and Costly below it. Below the cost threshold it is Low spend; with no spend at all it is a Zombie.
- **Product family thresholds** default to the same. A family adds up several products' spend, so a higher cost threshold (for example double) often suits it.
- **Store name and website** for the titles. The account name and the store's domain are fine.

## Step 5 — Search Volume (optional)

This tab answers "did sales drop because the market shrank?". It needs Keyword Planner's monthly volumes, which a Google Ads Script can't fetch. Propose 5 to 15 non-brand category keywords from the store's products (the product types and titles in the data), in the market's language, without close duplicates ("linen napkins", not also "linen napkin"). Then:

- With a connection that offers Keyword Planner historical metrics, fetch them (see `references/queries.md`).
- Otherwise give the user the Keyword Planner download steps in `references/queries.md` and wait for the file.
- If the user would rather skip it, skip it: the tab is left out and everything else still works.

```
python3 <skill-dir>/scripts/audittool.py planner <file> --run <store>-audit --market "<country>" --language "<language>"
```

## Step 6 — Product families

```
python3 <skill-dir>/scripts/audittool.py families --run <store>-audit
```

It groups product IDs into families: by the Shopify product ID when the IDs carry one (sizes and colours of one product share it), otherwise by the title without its size and variant words. It prints the biggest families with sample titles. Check that they read as real products. If two different products were merged or one product was split, edit the `family` column in `product-families.csv`. Never group products only because their titles look alike. Skip this check when the account has no Shopping products.

## Step 7 — Build

```
python3 <skill-dir>/scripts/audittool.py build --run <store>-audit --store "<Store name>" --domain <domain> \
    --margin 0.5 --roas 4 --cost 50 [--family-roas 4 --family-cost 100]
```

It prints the headline numbers (also saved to `summary.json`), the tabs built and any warnings. Read every warning and pass the relevant ones on: for example, spend on a network type Google doesn't name is counted in "Cross-network & other" so totals still add up.

Sense-check before delivering: an account with real Shopping spend should never come back with every product a Zombie, and the PMax + Shopping cost should not be more than the whole account's cost.

## Step 8 — Deliver and explain

Give the user:

1. The workbook's path, and how to open it in Google Sheets: upload it to Google Drive, open it, then **File > Save as Google Sheets**, and work in that copy. (In Google Sheets, File > Import > Upload also works.) It opens in Excel as it is. If this session has a Google Drive connection that can upload a file and convert it to Google Sheets, offer to do it.
2. The headline numbers, in three to six lines, from `summary.json`.
3. What stands out, in three to five points, each tied to a tab and a real number. `references/reading-the-report.md` says what to look for on each tab. Only state numbers the data contains; label anything else as a question to check.
4. How to use it: the cream cells are dropdowns and editable settings, and the hidden tabs hold the data the formulas read.
5. A privacy note: the workbook holds their account data, so check who it is shared with.

Offer natural next steps: a different date range, the Search Volume tab if it was skipped, or a closer look at one tab.

## Hard rules

- **Ask both gates every run** (Steps 1 and 2). Never assume a date range or a data route.
- **Never change anything in Google Ads.** Read-only queries only; the Google Ads Script only reads.
- **Every number comes from the data.** Never fill a missing query, month or product with estimates. A tab without its data is left out, and you say so.
- **Never guess the account** when a connection can see more than one.
- **Keep the workbook's brand header and footer credit** ("Built with the Big Flare Skills Pack").
