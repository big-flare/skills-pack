# Product Title Optimizer

Rewrite your Google Shopping product titles around what your shoppers actually search.

In Google Shopping there are no keywords to bid on. Google decides which searches your products show for mostly from their titles, so a word that isn't in the title is a search the product struggles to show for. Most titles are written for people browsing a website and use 40 to 60 of the 150 characters Google allows. This skill rebuilds each title from your own Google Ads search terms, Keyword Planner and your website: the most-searched phrase first, every character used, your brand at the end.

The new titles go into a supplemental feed that you upload to Google Merchant Center. It replaces the titles in Shopping without touching your store, your website or your main feed. Delete the supplemental feed and the old titles come back.

Part of the [Big Flare Skills Pack](https://github.com/big-flare/skills-pack).

## Watch it in action

[![This FREE AI Agent Optimises Your Google Shopping Feed](https://img.youtube.com/vi/2M446-a3xF4/maxresdefault.jpg)](https://www.youtube.com/watch?v=2M446-a3xF4)

[This FREE AI Agent Optimises Your Google Shopping Feed](https://www.youtube.com/watch?v=2M446-a3xF4): Daryl Mander explains why titles matter so much in Shopping and walks through the optimizer from start to finish. The video shows the original standalone version, which needed a GoMarble connection; this version works with any Google Ads connection, or none.

## What you get

A folder named `<store>-titles/` with three files you use:

- **`<store>-title-review.xlsx`**, a review spreadsheet. The Titles tab shows every product's original and new title side by side, with a character count that updates as you edit and turns red outside 130 to 150. The Research and Keywords tabs show what each title was built from.
- **`<store>-supplemental-titles.tsv`**, the supplemental feed, ready to upload to Merchant Center. One row per product: its item ID and the new title.
- **`<store>-title-review.html`**, a review page: every title before and after, the search phrases each one targets and where they came from, what was wrong with the originals, and anything worth a second look.

Edit any title you like in the spreadsheet, send it back and say "apply my edits". Claude re-checks every title (an edit can push a title over Google's 150-character limit) and rebuilds the feed file.

You also get step-by-step upload instructions for Merchant Center, and a simple test plan if you want to prove the new titles beat the old ones on a few top sellers first.

The folder also holds the run's working files. If a long run stops partway, ask Claude to carry on and it picks up from the first product without a title.

## What you need

- **Your product feed.** Ideally the file Merchant Center reads today: the feed your feed app produces, or a product download from Merchant Center. Google Shopping XML, TSV, CSV and Excel files all work. With Google Ads connected, Claude can pull the product list from your account instead.
  - The item IDs must match the IDs in Merchant Center exactly, or Merchant Center ignores the rows. That's why a store's own product export (a Shopify product CSV, for example) usually won't work: its IDs aren't the ones Merchant Center uses.
- **Your search terms (strongly recommended).** Claude asks how you want to supply them before it starts:
  1. **Google Ads connected:** if your Claude has a Google Ads connection, it pulls your search terms (and, if the connection offers it, Keyword Planner ideas).
  2. **A report:** download the search terms report from Google Ads and attach it. A Keyword Planner export helps too.
  3. **Skip it:** Claude builds the titles from your product pages and its own judgement. They're noticeably weaker without your real search data.
- **Which products to start with.** For a feed of more than 50 products, Claude asks. If it can see your clicks, it offers your top 50, 100 or 250 products and tells you what share of your Shopping clicks they get; otherwise it asks you to name your best sellers. Every variant of a product is included automatically.
- **Access to Google Merchant Center**, to upload the file yourself. The skill never uploads or changes anything, and it only ever reads from Google Ads.

Python is optional. If your Claude can run it, the skill uses a small helper script (plain Python, nothing to install) for the mechanical steps, including counting every title's characters exactly. Without it, Claude does the same steps by hand.

## How to use it

After installing, ask Claude in plain English and attach your feed. For example:

- "Optimise my Google Shopping product titles. Here's my feed and my search terms report."
- "Rewrite the titles for my top 100 products using my Google Ads search terms."
- "My Shopping titles are just product names. Can you make them match what people search?"
- "Write new titles for these 20 products and give me a supplemental feed."

Claude tells you which ID column, spelling and brand rule it will use, asks which products to do and where the search data should come from, then researches each category, writes in batches and saves as it goes. It checks every title against Google's rules before building the files.

## Install

The easiest route is to install the whole pack, which also gets you updates. See [Install](https://github.com/big-flare/skills-pack#install) in the main README.

To add just this skill to Claude Code:

```bash
git clone https://github.com/big-flare/skills-pack.git
cp -R skills-pack/skills/product-title-optimizer ~/.claude/skills/
```

Copying into `~/.claude/skills/` makes it available in every project. To keep it to one project, copy it into that project's `.claude/skills/` folder instead. A copied folder stays at the version you copied; pull the repo again to update.

Used the original standalone plugin ([big-flare/product-title-optimizer](https://github.com/big-flare/product-title-optimizer))? It stays available, but new versions ship here.

## What's in this folder

| File | What it does |
|---|---|
| `SKILL.md` | The workflow Claude follows, step by step |
| `references/title-guide.md` | How each title is built: structure, brand and variant rules, keyword priorities, examples and a self-check |
| `references/data-sources.md` | Where the products, search terms and Keyword Planner ideas come from, with the Google Ads queries and download steps |
| `references/merchant-center-rules.md` | Google's rules for titles and supplemental feeds, with the upload and test steps |
| `references/review-template.html` | The review page template. To use your brand colours, change the values in its `:root` block |
| `scripts/titletool.py` | The optional helper script: reads the feed and reports, matches search terms, checks titles and builds all three files |

## About Big Flare

[Big Flare](https://bigflare.com) is a Google Ads agency for ecommerce brands. This skill is a working version of the title work we do for our own clients. More free skills are in the [Big Flare Skills Pack](https://github.com/big-flare/skills-pack), and each one gets a video on the [Big Flare YouTube channel](https://www.youtube.com/channel/UCKEZmHEEOMuvT2PBU3owpQA).
