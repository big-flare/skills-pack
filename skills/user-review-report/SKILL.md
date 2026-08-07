---
name: user-review-report
description: Voice-of-customer research from real user reviews. Mines a brand's reviews across Trustpilot, regional review platforms, Reddit, editorial press, and the brand's own site, then turns the patterns into ad copy direction, a customer phrase bank, and landing page recommendations — delivered as a written analysis plus a polished HTML report. If Google Ads is connected it pulls the live ad copy automatically (or accepts a pasted/uploaded export) and grades every headline against what customers actually say. USE WHEN you want to know what customers actually say about a brand (yours or a competitor's), improve ad copy with real customer language, find messaging gaps, or research a market's objections. NOT for reputation management, review-response writing, or soliciting reviews.
version: 1.8.0
pack: big-flare-skills-pack
---

# User Review Report

Turn hundreds of real customer reviews into marketing you can use: ranked themes in customers' own words, the frictions that cause refunds and 1-stars, a gap analysis against your current ad copy, and a shareable HTML report.

The core idea: **your best copywriter is your existing customer base.** Reviews contain the exact language that convinces people like them — and the exact objections your marketing needs to defuse. This skill extracts both, systematically.

## Step 1 — Intake

Two gates before any research starts. Cover both in **one message** to the user — never a chain of one-question messages.

**Gate A — brand facts.** You need: **brand name + website**, **main market** (country — it decides which review platforms matter), and **product category**. If the user gave only a URL, infer these from the site and present them as assumptions to confirm rather than asking cold. Also invite the optional extras in the same message: known review platforms, competitor names, a specific question they want answered.

**Gate B — the ad-copy route. This question is MANDATORY — ask it every run, before any mining starts.** The ad-copy gap analysis is the highest-value section of the report, and which route supplies the data is the user's call, not yours. Ask which of the three paths applies even when you could start without it, and even when no Google Ads integration is visible in the session. Suggested phrasing:

> "One thing before I start: this report can grade your live ad copy against what your customers actually say — it's the most valuable section. I can **(1)** pull your ads automatically from Google Ads [offer only if an ads integration is available], **(2)** take a pasted or uploaded export (the Ads UI download or a Google Ads Editor export both work), or **(3)** skip it — the report will still cover everything else, but no gap analysis. Which would you like?"

**Do not begin Step 2 until the route is resolved.** Resolved means the user picked a path — and for path 1, confirmed which account — supplied the data, or explicitly said to skip. Assuming path 3 because the user didn't mention ad copy is **not** resolution: it silently deletes the report's best section. The only exception is when the user's opening message already supplied ad copy or explicitly declined it — then confirm your reading in the Gate A message instead of re-asking.

### Current ad copy — three paths

In order of preference:

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
2. **Manual upload or paste.** No integration? Ask the user to either paste their headlines and descriptions, or upload an export — the Google Ads UI's Ads download (CSV) and Google Ads Editor exports both work. Accept any reasonable format and extract the headline/description texts plus campaign/ad group names where present.
3. **Neither.** Skip the gap-analysis section rather than guessing. The opportunity map falls back to the brand's observed public marketing (see Step 5).

**Normalise, then forget the source.** Whichever path supplied the data, reduce it to one inventory before analysis: each unique headline and description with (a) how many ads use it, (b) which campaigns/ad groups (split brand vs non-brand where the naming makes it obvious), and (c) its performance label if available. From this point on, uploaded data and pulled data are treated identically. Two normalisation rules: **merge near-identical variants into one theme** ("Fast Absorbing & Non Sticky" / "Non-Sticky & Easy To Apply" are one claim — gap verdicts apply to themes, not string variants, so report combined usage counts); and if the account spans **multiple markets**, keep everything in the inventory, note the split, and weight the gap analysis toward the user's stated main market.

## Step 2 — Scope the review landscape

Before mining, find out where this brand's reviews actually live. Run searches like:

- `{brand} reviews {website domain}`
- `"{brand}" Trustpilot OR reviews site:trustpilot.com`
- Market-specific platform checks (see table)
- `{brand} review reddit`
- `{brand} review` (for editorial/blog roundups)

**By market** (regional platforms beyond Trustpilot):

| Market | Platforms to check |
|---|---|
| US | BBB, ConsumerAffairs, Google reviews, Yelp (local/service brands) |
| UK | Feefo, Reviews.io, Checkatrade / Trustatrader (trades), Mumsnet (parenting products) |
| Australia | ProductReview.com.au, MouthsOfMums (family products) |
| Canada | Google reviews, BBB, HomeStars (home services) |
| Germany / DACH | Trusted Shops, eKomi, idealo |
| France | Avis Vérifiés (Verified Reviews) |
| Netherlands | Kiyoh |
| India | MouthShut |

**By category** (vertical platforms — check whichever rows fit the brand):

| Category | Platforms to check |
|---|---|
| SaaS / software | G2, Capterra, GetApp, TrustRadius |
| Mobile apps | App Store + Google Play reviews (both — the audiences differ) |
| B2B services / agencies | Clutch, G2, Google reviews |
| Travel / hospitality | TripAdvisor, Booking.com, Google reviews |
| Restaurants / local | Google Maps, Yelp, OpenTable |
| Home services / trades | Angi (US), Checkatrade (UK), Houzz, HomeStars (CA) |
| Beauty / skincare | Sephora & Ulta listing reviews, MakeupAlley, Influenster |
| Health / supplements | Amazon, iHerb, condition-specific subreddits |
| Baby / parenting | Mumsnet, BabyCenter, MouthsOfMums |
| Fashion / apparel | Own-site + retailer listings (ASOS etc.), Reddit sizing threads |
| Electronics | Retailer listings (Best Buy, Currys), Rtings (editorial), Reddit |
| Courses / education | Trustpilot, Reddit, Course Report / Class Central |

**Wherever the brand actually sells** — reviews accumulate on the *listing*, not just the brand: Amazon,
Etsy, eBay, Walmart.com, and big-box retailer product pages all carry their own review corpora. Check every
marketplace the brand's site links to.

**Always, any brand:** the brand's own on-site review widget (Yotpo / Okendo / Judge.me — often the single
largest corpus, and always the most positive-skewed), Facebook page reviews, Reddit, and YouTube review
videos plus their comment threads (comments are voice-of-customer too).

Record what exists and roughly how many reviews each source holds. Aim to cover **at least three independent sources** — a single platform gives a skewed picture (each platform attracts different complaint types). The tables are routing hints, not a checklist: a typical brand has reviews on 3-6 of these, not all of them, and five minutes of scoping tells you which.

## Step 3 — Mine the reviews

**The read target is a FLOOR, not a cap** — scale it to the size of the visible corpus:

| Visible corpus (all sources) | Read in full |
|---|---|
| Under ~500 reviews | Everything you can access |
| ~500 – 5,000 | 150 – 250 |
| Over 5,000 | 250 – 400 |

Whatever the tier, the non-negotiable is the same: **the complete low-star corpus always gets read** — that
matters more than the total count. In practice the binding constraint is platform access (login walls,
pagination gates, 403s), not reading time; when access cuts you off below the tier target, report the
shortfall in your caveats rather than padding the number. Read `references/mining-playbook.md` before
starting — it covers per-platform access quirks and sampling traps.

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
4. **Gap analysis** (if current ad copy was pulled or uploaded) — table: each live copy theme vs the review verdict, weighted by actual usage ("your most-used headline, in 6 ads, is also the most-disputed claim in negative reviews" is the highest-leverage finding this skill produces). Flag: claims reviews dispute (worst when in heavy rotation), themes reviews support that copy underuses (e.g. one headline for a top-3 theme), and proof language reviews offer that copy ignores. If performance labels came with the data, cross-reference them — a Google-rated LOW asset that reviews also dispute is a confident kill; a BEST-rated asset aligned with a top theme is the one to multiply. Split brand vs non-brand campaigns where distinguishable — non-brand copy is where VoC language matters most.
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
