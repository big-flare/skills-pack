# Big Flare Skills Pack

Free Claude skills for ecommerce marketers, from the team at [Big Flare](https://bigflare.com).

Each skill is a complete, repeatable workflow — the same processes we run for our own Google Ads clients, packaged so Claude can run them for you. Install once and every skill (including future ones) is available in your Claude.

## What's inside

| Skill | What it does | Video |
|---|---|---|
| [user-review-report](skills/user-review-report/) | Mines a brand's customer reviews across Trustpilot, regional review platforms, Reddit, and editorial press, then turns the patterns into ad copy direction, a voice-of-customer phrase bank, and landing page recommendations — delivered as a written analysis plus a polished HTML report. Got Google Ads connected? It pulls your live ad copy and grades every headline against what customers actually say (a pasted export works too). | [Watch](https://www.youtube.com/watch?v=YRlBERum5Nw) |
| [product-description-writer](skills/product-description-writer/) | Rewrites your Google Shopping product descriptions from each product's own feed data, so every product and every variant gets its own clear, fact-only description. You get a supplemental feed to upload to Google Merchant Center (it replaces the descriptions in Shopping without touching your store or main feed), a before/after review page that flags any facts your sources disagree on, and a simple A/B test plan. | Coming soon |
| [product-title-optimizer](skills/product-title-optimizer/) | Rewrites your Google Shopping product titles around what your shoppers actually search. It uses your own Google Ads search terms (pulled automatically if Google Ads is connected, or from a report you download), Keyword Planner and your website, and gives you a supplemental feed for Google Merchant Center (it replaces the titles in Shopping without touching your store or main feed), a review spreadsheet where you can edit any title before uploading, and a before/after review page. | [Watch](https://www.youtube.com/watch?v=2M446-a3xF4) |
| [google-ads-audit-analysis](skills/google-ads-audit-analysis/) | Builds the analysis behind a Google Ads audit: one workbook, opened in Google Sheets, that shows where an ecommerce account's money goes. Monthly performance with gross profit after ad spend, where Performance Max spend really goes (Shopping, Search, YouTube, Display, Gmail), every product sorted into Profitable, Costly, Low spend and Zombies, market demand from Keyword Planner, and the converting searches you have no keyword for. Data comes from a Google Ads connection or a read-only Google Ads Script you run in two minutes. | Coming soon |

The Product Title Optimizer used to be its own plugin ([big-flare/product-title-optimizer](https://github.com/big-flare/product-title-optimizer)). It now lives in this pack, without needing a separate Google Ads connector, and new versions ship here.

More skills are added over time — watch the [Big Flare YouTube channel](https://www.youtube.com/channel/UCKEZmHEEOMuvT2PBU3owpQA) to see each one in action when it lands.

## What's a Claude skill?

A skill is a set of instructions that teaches Claude a repeatable expert workflow. When you ask Claude for something a skill covers ("what do customers say about my brand?"), Claude loads the skill and follows the process — same steps, same quality bar, every time.

## Install

### Claude Code (recommended — gets you everything, plus updates)

```
/plugin marketplace add big-flare/skills-pack
/plugin install bigflare-skills-pack@bigflare-skills-pack
```

### Claude Desktop (Cowork personal plugin)

1. [Download this repo as a zip](https://github.com/big-flare/skills-pack/archive/refs/heads/main.zip) and unzip it.
2. Re-zip the repo folder's *contents* so `.claude-plugin/` sits at the zip root.
3. Claude Desktop → Cowork → Customize → Personal plugins → **+** → select the zip.

### Manual (single skill, any Claude Code project)

Copy the skill folder into your project:

```bash
cp -R skills/user-review-report /path/to/your/project/.claude/skills/
```

## How these skills are built

- **Self-contained** — everything a skill needs lives in its folder. No external dependencies, no accounts, no API keys required.
- **Baseline tools only** — skills run on Claude's standard web search and file tools. Where an integration helps (e.g. a Google Ads connection), it's optional and the skill works without it. Some skills include a small helper script (plain Python, nothing to install) that makes the mechanical steps faster and more reliable; they still work without it.
- **Works everywhere** — Claude Code, Claude Desktop (Cowork), and claude.ai.
- **Re-brandable output** — report templates use a single design-token block you can swap for your own brand colours.

## Who is Big Flare?

We're a Google Ads agency for ecommerce brands — 18 years running paid traffic, $150M+ in managed spend. These skills are working versions of processes we use with clients. If you'd rather have the humans (and their AI) run your ads: [bigflare.com](https://bigflare.com).

## License & support

MIT — use them, adapt them, share them. Skills are provided as-is; they get updated when we ship new versions alongside our videos. Issues and PRs are welcome but response isn't guaranteed.
