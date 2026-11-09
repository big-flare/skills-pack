# Product Description Writer

Give every product and every variant in your Google Shopping feed its own clear, fact-only description.

Many feed descriptions are a product page's bullet list with the formatting stripped out, which leaves one long block with no full stops. Often every size and colour of a product shares the same text. This skill rewrites each description from that product's own feed data, so it names the exact product and variant and reads as proper sentences. It never invents facts, numbers or claims.

The new descriptions go into a supplemental feed that you upload to Google Merchant Center. It replaces the descriptions in Shopping without touching your store, your website or your main feed. Delete the supplemental feed and the old descriptions come back.

Part of the [Big Flare Skills Pack](https://github.com/big-flare/skills-pack).

## Watch it in action

Video coming soon on the [Big Flare YouTube channel](https://www.youtube.com/channel/UCKEZmHEEOMuvT2PBU3owpQA).

## What you get

A folder named `<store>-descriptions/` with two files you use:

- **`<store>-supplemental-descriptions.tsv`**, the supplemental feed, ready to upload to Merchant Center. One row per product: its item ID and the new description.
- **`<store>-description-review.html`**, a review page to read before you upload. It shows every product's description before and after, what was wrong with the originals, and a "Decisions for you" list.

The decisions list matters. When your feed and your product page disagree on a fact (two different weights, say), the skill leaves that fact out and flags it for you rather than picking a side.

You also get step-by-step upload instructions for Merchant Center and a simple A/B test plan, so you can prove the new descriptions beat the old ones on a few top sellers before rolling them out.

The folder also holds the run's working files. If a long run stops partway, ask Claude to carry on and it picks up from the first product without a description.

## What you need

- **Your product feed.** Ideally the file Merchant Center reads today: the feed your feed app produces, or a product download from Merchant Center. Google Shopping XML, TSV, CSV and Excel files all work.
  - The item IDs in the file must match the IDs in Merchant Center exactly, or Merchant Center ignores the rows. That's why a store's own product export (a Shopify product CSV, for example) usually won't work: its IDs aren't the ones Merchant Center uses.
- **Which products to start with.** For a feed of more than 50 products, Claude asks. It recommends 10 to 25 of your best sellers: you can read every description before uploading, and best sellers are where better descriptions pay back fastest. Every variant of a product you name is included automatically.
- **Access to Google Merchant Center**, to upload the file yourself. The skill never uploads or changes anything.

Python is optional. If your Claude can run it, the skill uses a small helper script (plain Python, nothing to install) for the mechanical steps. Without it, Claude does the same steps by hand.

## How to use it

After installing, ask Claude in plain English and attach your feed. For example:

- "Rewrite the Google Shopping descriptions for my best sellers. Here's my feed."
- "My feed descriptions are just stripped bullet lists. Can you fix them?"
- "Every size of my products shares one description. Give each variant its own."
- "Write new descriptions for these 20 products and give me a supplemental feed."

Claude tells you which ID column and spelling it will use, asks which products to do, then writes in batches and saves as it goes. It checks every description against the product's data before building the files.

## Install

The easiest route is to install the whole pack, which also gets you updates. See [Install](https://github.com/big-flare/skills-pack#install) in the main README.

To add just this skill to Claude Code:

```bash
git clone https://github.com/big-flare/skills-pack.git
cp -R skills-pack/skills/product-description-writer ~/.claude/skills/
```

Copying into `~/.claude/skills/` makes it available in every project. To keep it to one project, copy it into that project's `.claude/skills/` folder instead. A copied folder stays at the version you copied; pull the repo again to update.

## What's in this folder

| File | What it does |
|---|---|
| `SKILL.md` | The workflow Claude follows, step by step |
| `references/writing-guide.md` | How each description is written: the recipe, variant and conflict rules, what to leave out, and a worked example |
| `references/merchant-center-rules.md` | Google's rules for descriptions and supplemental feeds, with the upload and A/B test steps |
| `references/review-template.html` | The review page template. To use your brand colours, change the values in its `:root` block |
| `scripts/feedtool.py` | The optional helper script: reads the feed, saves drafts, checks them and builds both files |

## About Big Flare

[Big Flare](https://bigflare.com) is a Google Ads agency for ecommerce brands. This skill is a working version of the feed work we do for our own clients. More free skills are in the [Big Flare Skills Pack](https://github.com/big-flare/skills-pack), and each one gets a video on the [Big Flare YouTube channel](https://www.youtube.com/channel/UCKEZmHEEOMuvT2PBU3owpQA).
