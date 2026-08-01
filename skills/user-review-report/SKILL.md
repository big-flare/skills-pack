---
name: user-review-report
description: Voice-of-customer research from real user reviews. Mines a brand's reviews across Trustpilot, regional review platforms, Reddit, editorial press, and the brand's own site, then turns the patterns into ad copy direction, a customer phrase bank, and landing page recommendations — delivered as a written analysis plus a polished HTML report. USE WHEN you want to know what customers actually say about a brand (yours or a competitor's), improve ad copy with real customer language, find messaging gaps, or research a market's objections. NOT for reputation management, review-response writing, or soliciting reviews.
version: 1.3.0
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
4. *Optional:* known review platforms, current ad headlines/descriptions (pasted in), competitor names, a specific question they want answered

If the user has a Google Ads integration connected, offer to pull their live headlines/descriptions instead of asking for a paste. If they have neither, skip the gap analysis section rather than guessing.

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
4. **Gap analysis** (if current ad copy provided) — table: each live copy theme vs the review verdict. Flag: claims reviews dispute, themes reviews support that copy underuses, and proof language reviews offer that copy ignores.
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
