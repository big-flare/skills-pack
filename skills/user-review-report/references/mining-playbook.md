# Review Mining Playbook

Per-platform access quirks and sampling traps, learned the hard way. Read before mining.

## Access quirks by platform

**Trustpilot**
- Often blocks plain HTTP fetches (403). Escalate through: the country subdomain (`au.trustpilot.com`, `uk.trustpilot.com`), the star-rating filters (`?stars=1`, `?stars=2`, …), a browser tool if you have one. **All of these can 403 too** — in some environments no direct Trustpilot route works at all. When that happens, cover Trustpilot at *theme level* via site-limited web searches (`site:trustpilot.com {brand} {theme keyword}`), don't count it toward verbatim evidence, and disclose the access failure in your caveats.
- Deep pagination (typically past page ~10) is **login-gated** — you'll silently hit a wall. The star filters, where they work, let you read the complete low-star corpus even when you can't page through everything.
- Check the review timeline: many brands have a burst of short, invited, service-focused reviews from launch, then a gap, then organic reviews. Weight organic ("unprompted") reviews higher for product truth.
- Note Trustpilot's own trust flags ("has not asked for reviews", reply rate to negatives) — useful colour.

**ProductReview.com.au (and similar regional platforms)**
- Pagination often starts returning 403 after ~10 pages. Get the negative reviews early via rating filters or search.
- Watch for **incentivised review clusters** — badges like "Fair Incentive" or a burst of reviews in one month from a product-trial campaign. These skew positive and gush-y; weight them below organic verified purchases, and say so in your caveats.

**Reddit**
- Direct reddit.com fetches are frequently blocked — and your fetch tool may refuse `old.reddit.com` and `web.archive.org` outright (tool-level blocks, not site-level). **The most reliable baseline route is the pullpush.io search archive** (`https://api.pullpush.io/reddit/search/comment/?q={brand}` and `/submission/`) — try it early rather than last. A browser tool works too if available; site-limited web search (`site:reddit.com "{brand}"`) surfaces threads as a final fallback.
- The most valuable Reddit material is usually NOT dedicated review threads — it's drive-by mentions in condition/problem threads ("what worked for your X?"). Search the brand name, but also search the problem category.
- Reddit is where the skeptics live. Capture the skepticism verbatim — the exact objections ("does this even work / is it placebo / the science says...") are what your landing page has to answer. Don't sanitise it out.

**Brand's own site**
- Usually the largest review corpus and the most positive-skewed (some brands gate or filter). Use it for: total counts, star distribution, featured-quote style, and the brand's own claims to verify. Don't let it dominate theme ranking — it lacks the negative tail.

**Editorial / blog roundups**
- Useful for competitive positioning (who else is recommended, at what price) and for expert framing. But beware: statistics in roundups are often supplied by the brand's PR ("X% of users report..."). Treat as brand-supplied unless independently sourced.

**Amazon (if the brand sells there)**
- Sort by "most recent" AND read the critical-review filter. Amazon's negative reviews skew heavily toward fulfilment issues — separate those from product complaints.
- Amazon pages often render as an empty JavaScript shell to fetch tools. If you get no content, don't fight it — cover Amazon via search snippets at theme level and disclose.

**Hard walls — general rules**
- **Never attempt to bypass a CAPTCHA, bot check, or login wall.** A walled source gets covered at theme level via search, or dropped — always disclosed in caveats.
- **Rate limiting (429):** back off and try the source again later in the session; if it persists, fall back to search-indexed content and disclose.
- **Google reviews** have no reliable headless route — treat the star rating/count (visible in search) as context and don't plan on mining them.
- **Summarised search results:** some environments' web search returns AI-summarised results rather than raw page snippets. Text harvested that way is paraphrase-risk — usable for theme identification, **never as a verbatim quote**. Only quote text you read on an actual page.

## Sampling traps

1. **Positive-skew default.** Every platform surfaces positive reviews first. If you only read the default sort, you'll write a puff piece. Deliberately seek out the complete 1-3 star corpus.
2. **Recency vs history.** Products change. Note review dates; a complaint cluster from 3 years ago may be fixed. Prefer the last 12-24 months for frequency estimates, use older reviews for durable themes.
3. **One platform ≠ the market.** Trustpilot attracts service complaints; product platforms attract product feedback; Reddit attracts skeptics. Three sources minimum before ranking themes.
4. **Quote truncation.** Search snippets truncate. Mark truncations honestly; never reconstruct or "complete" a quote.
5. **Small-N humility.** If you read 40 reviews, say "~40 reviews read" and present frequencies as rough. Never imply a census you didn't do.
6. **Wrong third-party aggregators.** Review-aggregator and affiliate sites misreport primary-source numbers (e.g. claiming "400+ complaints" when the primary page shows 4). When an aggregator conflicts with the primary source, the primary source wins — exclude the aggregator and note why.
7. **Synthetic quotes on affiliate roundups.** AI-generated affiliate pages fabricate "user quotes" (often attributed to Reddit). If a quote can't be traced to a real review or thread, it doesn't exist for your purposes.
8. **Wrong product in the thread.** In long threads, highly-quoted comments sometimes review a *competitor's* product. Before capturing a quote, confirm what it's actually about.

## What to capture per review (mental checklist)

- Verbatim key phrases (the exact words a customer would type into Google)
- The problem they were trying to solve, in their words
- What they tried before (competitors, substitutes, "nothing worked")
- Who they are (any demographic/situation signal)
- The proof device they offer (timeline, measurement, before/after, "removal test")
- For negatives: was the failure product, expectation, or operations?
