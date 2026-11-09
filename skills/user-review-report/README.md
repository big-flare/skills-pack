# User Review Report

Find out what customers actually say about a brand, then use their words in your ads.

This skill reads a brand's reviews on Trustpilot, regional review sites, Reddit, editorial roundups and the brand's own site. It ranks what customers love and what frustrates them, in their own words. You get a written analysis and a polished HTML report with ad copy direction, a customer phrase bank and landing page recommendations. Connect Google Ads (or paste an export) and it also grades every live headline against what customers say.

Part of the [Big Flare Skills Pack](https://github.com/big-flare/skills-pack).

## Watch it in action

[![Skyrocket Your Google Ads CTR With Customer Review Mining (Free Tool)](https://img.youtube.com/vi/YRlBERum5Nw/maxresdefault.jpg)](https://www.youtube.com/watch?v=YRlBERum5Nw)

[Skyrocket Your Google Ads CTR With Customer Review Mining (Free Tool)](https://www.youtube.com/watch?v=YRlBERum5Nw): Daryl Mander runs the skill on a brand you'll recognise, walks through the report, then runs it again with Google Ads data attached to show the headline gap table.

## What you get

Two files, plus a short summary of the biggest findings:

- **`{brand}-user-review-analysis.md`**, the working analysis: what customers love and what frustrates them (ranked by how often they come up, with verbatim quotes), a phrase bank grouped by positioning angle, copy ideas for each customer segment, landing page opportunities, claims to stop leading with, and every source with its review counts.
- **`{brand}-user-review-report.html`**, a shareable report built from the analysis. It includes a review landscape chart, a love-versus-friction chart that shows the whole picture at a glance, and an opportunity map of the themes customers care about against what the brand's marketing says today.

With ad copy attached, the report adds a **gap table**: each headline theme in your live ads, how many ads use it, and whether reviews back it up or dispute it. A heavily used headline that customers complain about is the kind of finding this table exists to catch.

## What you need

- **The brand's name and website.** A URL is enough to start. Claude works out the main market and product category from the site and asks you to confirm them.
- **Your ad copy (optional, but it unlocks the best section).** Claude asks how you want to supply it before it starts:
  1. **Google Ads connected:** if your Claude has a Google Ads connection, it pulls every live responsive search ad's headlines and descriptions.
  2. **An export or a paste:** the Ads download (CSV) from the Google Ads interface, a Google Ads Editor export, or headlines pasted into the chat.
  3. **Skip it:** you get everything except the gap table.
- **Web search**, which Claude has as standard. No accounts or API keys needed.

It works on any brand, not only your own. Run it on a competitor to see what their customers praise and complain about.

## How to use it

After installing, ask Claude in plain English. For example:

- "What do customers actually say about [brand]? Their site is [website]."
- "Run a user review report on my store, [website]. Here's my Google Ads export."
- "Grade my Google Ads headlines against my customer reviews."
- "What do people complain about in reviews of my competitor, [brand]?"

Claude confirms the brand details and the ad copy route in one message, then gets to work. Bigger brands with thousands of reviews take longer, because it reads every low-star review it can reach.

## Install

The easiest route is to install the whole pack, which also gets you updates. See [Install](https://github.com/big-flare/skills-pack#install) in the main README.

To add just this skill to Claude Code:

```bash
git clone https://github.com/big-flare/skills-pack.git
cp -R skills-pack/skills/user-review-report ~/.claude/skills/
```

Copying into `~/.claude/skills/` makes it available in every project. To keep it to one project, copy it into that project's `.claude/skills/` folder instead. A copied folder stays at the version you copied; pull the repo again to update.

## What's in this folder

| File | What it does |
|---|---|
| `SKILL.md` | The workflow Claude follows, step by step |
| `references/mining-playbook.md` | How to read each review platform, its access quirks and sampling traps |
| `references/report-template.html` | The HTML report template. To use your brand colours, change the values in its `:root` block |

## About Big Flare

[Big Flare](https://bigflare.com) is a Google Ads agency for ecommerce brands. This skill is a working version of the review research we do for our own clients. More free skills are in the [Big Flare Skills Pack](https://github.com/big-flare/skills-pack), and each one gets a video on the [Big Flare YouTube channel](https://www.youtube.com/channel/UCKEZmHEEOMuvT2PBU3owpQA).
