---
name: user-review-report
description: Voice-of-customer research from real user reviews. Mines a brand's reviews across Trustpilot, regional review platforms, Reddit, editorial press, and the brand's own site, then turns the patterns into ad copy direction, a customer phrase bank, and landing page recommendations — delivered as a written analysis plus a polished HTML report. It also grades the brand's live ad copy against what customers actually say: pulled from Google Ads if connected, from a pasted or uploaded export, or — for any competitor, where neither is possible — harvested from the public Google Ads Transparency Center. USE WHEN you want to know what customers actually say about a brand (yours or a competitor's), improve ad copy with real customer language, find messaging gaps, audit a competitor's advertising against their own reviews, or research a market's objections. NOT for reputation management, review-response writing, or soliciting reviews.
version: 1.5.0
pack: big-flare-skills-pack
---

# User Review Report

Turn hundreds of real customer reviews into marketing you can use: ranked themes in customers' own words, the frictions that cause refunds and 1-stars, a gap analysis against your current ad copy, and a shareable HTML report.

The core idea: **your best copywriter is your existing customer base.** Reviews contain the exact language that convinces people like them — and the exact objections your marketing needs to defuse. This skill extracts both, systematically.

## Step 1 — Intake

Ask the user for (don't proceed until you have the first three):

1. **Brand name** and **website**
2. **Main market** (country — this decides which review platforms matter)
3. **Product category** (what they sell, roughly)
4. *Optional:* known review platforms, competitor names, a specific question they want answered
5. **Current ad copy** — see the four paths below. Worth 30 seconds of setup: it upgrades the gap analysis and the opportunity map from inferred to exact.

### Current ad copy — four paths

**Ordered by data quality, gated by capability — these are different axes.** Path 3 gives better data than nothing but needs browser automation, so it ranks above "nothing" in quality yet below paths 1-2 in portability. Work down the list and take the first path that is both *available* and *appropriate*; each path names what it degrades to.

**Whose brand is being analysed changes the routing:**
- **The user's own brand** → paths 1 and 2 are strictly better (real asset lists, true usage counts, performance labels). Offer those first and say why. Only fall to path 3 if the user declines or genuinely can't supply the data — and tell them plainly it's the weaker source.
- **A competitor** → paths 1 and 2 are impossible; you will never have their account or their export. Go straight to path 3. This is what makes competitor gap analysis work at all.

1. **Google Ads connected.** If a Google Ads integration/tool is available in the session, use it — confirm the right account with the user, then pull every enabled responsive search ad's headlines and descriptions with campaign and ad group names. Example GAQL:
   ```
   SELECT campaign.name, ad_group.name,
          ad_group_ad.ad.responsive_search_ad.headlines,
          ad_group_ad.ad.responsive_search_ad.descriptions
   FROM ad_group_ad
   WHERE ad_group_ad.status = 'ENABLED' AND campaign.status = 'ENABLED'
     AND ad_group.status = 'ENABLED'
     AND ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'
   ```
   If asset performance labels come back with the headlines (`assetPerformanceLabel`: LOW/GOOD/BEST), keep them — they enable an extra cross-reference in Step 4. Two realities of live pulls: (a) accounts with many RSAs return more data than fits in a tool result — expect to process the saved output with a small script, or page the query with `LIMIT`/campaign filters; (b) recently refreshed accounts return mostly PENDING labels — when few assets carry real labels, treat the label cross-reference as directional colour, not evidence, and say so.
   *Degrades to:* path 2 if no Google Ads tool is available or the user can't grant access.
2. **Manual upload or paste.** No integration? Ask the user to either paste their headlines and descriptions, or upload an export — the Google Ads UI's Ads download (CSV) and Google Ads Editor exports both work. Accept any reasonable format and extract the headline/description texts plus campaign/ad group names where present. This path works on every surface.
   *Degrades to:* path 3 if the user has no export to hand, or the brand isn't theirs.
3. **Google Ads Transparency Center harvest** *(requires browser automation — a tool that can navigate, screenshot and scroll).* Google publishes every advertiser's currently-running ads. Harvest them to build the inventory from public data. **Full procedure and gotchas: `references/mining-playbook.md` → "Harvesting ads from the Google Ads Transparency Center".** In outline: resolve the advertiser via search autocomplete (take the *verified* entity), open its page with `&format=TEXT` to isolate search ads, then capture and read the rendered ads.
   - **Default stop:** ~150 ads, or 3 consecutive captures yielding no new unique headline, whichever comes first. Then report coverage honestly ("142 of ~600 text ads captured") and offer to go deeper. Don't silently harvest a full corpus — it's slow and expensive for the user.
   - **Scope guard:** only harvest the brand whose reviews you are analysing. This path exists to feed the gap table, not to be a general ad-lookup tool.
   - **What you don't get:** no performance labels (LOW/GOOD/BEST live only inside the advertiser's account) and no RSA asset pools — you see assembled ads as served. Both limits must appear in your caveats.
   - **Save the harvest** as a dated working file (`{brand}-ad-inventory-YYYY-MM-DD.md`) alongside the analysis, so re-runs and follow-up questions don't re-scrape.
   *Degrades to:* path 4 if no browser tool is available, the advertiser can't be found, or the site blocks you. Say which, don't fail the run.
4. **None available.** Skip the gap-analysis section rather than guessing. The opportunity map falls back to the brand's observed public marketing (see Step 5).

**Normalise, then forget the source.** Whichever path supplied the data, reduce it to one inventory before analysis: each unique headline and description with (a) how many ads use it, (b) which campaigns/ad groups (split brand vs non-brand where the naming makes it obvious), and (c) its performance label if available. From this point on, every path's data is treated identically.

**One exception you must not blur — what the frequency count means.** Paths 1-2 count *asset usage*: how many ads draw on that headline asset. Path 3 counts *served creatives*: how many of the ads you captured displayed that line, because the Transparency Center never exposes the RSA asset pool. These are related but not the same number. When the inventory came from path 3, phrase every finding as **"appears across N of the ads we captured"** — never "this asset is used in N ads." The stronger phrasing would overstate what public data can support. Two normalisation rules: **merge near-identical variants into one theme** ("Fast Absorbing & Non Sticky" / "Non-Sticky & Easy To Apply" are one claim — gap verdicts apply to themes, not string variants, so report combined usage counts); and if the account spans **multiple markets**, keep everything in the inventory, note the split, and weight the gap analysis toward the user's stated main market.

## Step 2 — Scope the review landscape

Before mining, find out where this brand's reviews actually live. Run searches like:

- `{brand} reviews {website domain}`
- `"{brand}" Trustpilot OR reviews site:trustpilot.com`
- Market-specific platform checks (see table)
- `{brand} review reddit`
- `{brand} review` (for editorial/blog roundups)

| Market | Platforms to check beyond Trustpilot |
|---|---|
| Australia | ProductReview.com.au |
| UK | Feefo, Reviews.io |
| US | BBB, ConsumerAffairs, Google reviews |
| SaaS/software (any) | G2, Capterra, GetApp |
| Sold on Amazon | Amazon reviews for their listings |
| Any DTC brand | Their own site's review widget (often the largest corpus) |

Record what exists and roughly how many reviews each source holds. Aim to cover **at least three independent sources** — a single platform gives a skewed picture (each platform attracts different complaint types).

## Step 3 — Mine the reviews

**Target: 150+ customer statements read in full**, more if the brand is large. Read `references/mining-playbook.md` before starting — it covers per-platform access quirks and sampling traps.

Counting rule: a review "counts" only if you read its actual text on a page (or a complete archived copy) — screening search results or summaries does not count. When tooling means you screen many but fully read fewer, report both numbers ("~800 screened, ~140 read verbatim") in your caveats.

Non-negotiables:

- **Read the complete low-star corpus wherever possible.** Negative reviews are few and disproportionately valuable — read every 1-3 star review you can access, not just a sample.
- **Capture VERBATIM quotes** — exact customer words, in quotes. Paraphrases are worthless for copy work; the whole point is the customer's own language.
- **Estimate theme frequency honestly** — "~60% of positive reviews mention X" based on what you actually read, and say how many you read.
- **Note who the reviewers are** — audience segments visible in the language (parents, athletes, older buyers, professionals, etc.).
- **Capture comparisons** — what alternatives do reviewers mention (competitors, substitute products, "I used to use...")?
- If subagents/parallel tasks are available, split sources across them (one per platform, one for Reddit + editorial). Otherwise work through sources sequentially — the output quality matters, not the speed.

## Step 4 — Synthesise

Write the analysis file (`{brand}-user-review-analysis.md`) with these sections:

1. **Header** — date, sources with review counts and how many you read, purpose.
2. **What customers love** — themes RANKED by frequency, each with: estimated % of positive reviews, what specifically customers describe, and 5-10 verbatim quotes.
3. **What frustrates customers** — ranked the same way. Distinguish product frictions (copy-relevant) from operational issues (shipping, support — flag but don't over-weight for messaging).
4. **Gap analysis** (whenever Step 1 produced an inventory by any of paths 1-3) — table: each live copy theme vs the review verdict, weighted by actual usage ("your most-used headline, in 6 ads, is also the most-disputed claim in negative reviews" is the highest-leverage finding this skill produces). If the inventory came from a Transparency Center harvest, keep the weaker phrasing — "appears across N of the ads we captured" — and state the coverage. Flag: claims reviews dispute (worst when in heavy rotation), themes reviews support that copy underuses (e.g. one headline for a top-3 theme), and proof language reviews offer that copy ignores. If performance labels came with the data, cross-reference them — a Google-rated LOW asset that reviews also dispute is a confident kill; a BEST-rated asset aligned with a top theme is the one to multiply. Split brand vs non-brand campaigns where distinguishable — non-brand copy is where VoC language matters most.
5. **Voice-of-customer phrase bank** — real customer phrasings grouped by positioning angle, ready to adapt into headlines.
6. **Copy recommendations by audience segment** — for each segment found in Step 3: what to lead with, an example headline direction, and why.
7. **Landing page opportunities** — what the reviews say the LP should pre-empt, prove, or promise. Honest expectation-setting that reviews show converts (e.g. realistic timelines) belongs here.
8. **What NOT to lead with** — claims that negative reviews dispute, overpromises that create the 1-star pipeline, unverifiable superlatives.
9. **Sources & corpus caveats** — every source with URL and counts, plus honest limits (login-gated pages, incentivised-review clusters, archive gaps).

Synthesis quality bar:

- Every claim traces to something you read. No invented quotes, ever.
- Cross-check the brand's own marketing claims against what reviews support (e.g. a "10,000+ five-star reviews" ad claim vs the actual visible counts) — verifiable claims beat inflated ones.
- Look for the **proof devices customers invent themselves** (before/after stories, "I stopped using it and noticed", measurements, photos) — these beat any manufactured claim.
- Treat brand-supplied statistics found in editorial roundups as brand-supplied, not independent.

## Step 5 — Build the HTML report

Generate `{brand}-user-review-report.html` following `references/report-template.html` — it defines the structure (cover → stat row → executive summary → review landscape → message opportunity map → butterfly chart → loves → frustrations → gap table → phrase bank → segments → LP opportunities → don'ts → sources) and a neutral, professional design with a single token block.

- **Assemble the report by splicing the template file programmatically** — copy the head, CSS, brand header, and footer verbatim with a script and generate only the content sections. Never retype the template by hand: the brand logo is a long base64 block that does not survive manual reproduction.
- Keep the template's `:root` tokens unless the user asks for their brand colours — then swap only the token values.
- Populate every section from the analysis file. The report is the shareable artifact; the markdown is the working file.
- **The executive summary is ONE tight paragraph** (4-6 sentences): the dominant theme + its proof device, the top frictions, the single biggest opportunity. Resist the second paragraph — the visuals right below it carry the detail.
- **Populate the three visuals from your real numbers** — they exist to make the findings scannable, never to decorate:
  - *Review landscape* (always): one row per source, bar filled to rating/5, brand-controlled sources marked with the muted `own` class.
  - *Butterfly chart* (always): every major love and friction theme as one interleaved, frequency-sorted chart — this is the whole report at a glance.
  - *Opportunity matrix* (near the top, right after the review landscape): each major theme placed by mention frequency × presence in current marketing. With the gap analysis, base it on the ad copy; without ad copy, base it on the brand's public marketing claims you actually observed during research. Either way, state the basis in the note under the matrix. Drop it only when you have no honest read on the brand's current messaging.
  - If you don't have honest numbers for a visual, drop that visual — never invent data to fill a chart.
- If you skipped the gap analysis (no ad copy available), drop the gap-table section and renumber the remaining section eyebrows so there's no gap. The opportunity matrix up top is unaffected — it stays whenever an honest messaging basis exists.
- Keep the brand header and the footer credit intact.

## Step 6 — Deliver

Give the user: the analysis file, the HTML report, and a 5-8 bullet summary of the highest-leverage findings — lead with anything their current copy gets wrong and the single biggest untapped theme.

Offer natural next steps: draft the missing ad copy, build a keyword list from the phrase bank, or repeat the analysis on a competitor.
