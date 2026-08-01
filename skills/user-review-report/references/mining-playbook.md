# Review Mining Playbook

Per-platform access quirks and sampling traps, learned the hard way. Read before mining.

## Access quirks by platform

**Trustpilot**
- Often blocks plain HTTP fetches (403). If a fetch fails, try the country subdomain (`au.trustpilot.com`, `uk.trustpilot.com`), a browser tool if available, or fall back to site-limited web searches (`site:trustpilot.com {brand} {theme keyword}`) and harvest quotes from result snippets.
- Deep pagination (typically past page ~10) is **login-gated** — you'll silently hit a wall. Work around it with the star-rating filters (`?stars=1`, `?stars=2`, …), which let you read the complete low-star corpus even when you can't page through everything.
- Check the review timeline: many brands have a burst of short, invited, service-focused reviews from launch, then a gap, then organic reviews. Weight organic ("unprompted") reviews higher for product truth.
- Note Trustpilot's own trust flags ("has not asked for reviews", reply rate to negatives) — useful colour.

**ProductReview.com.au (and similar regional platforms)**
- Pagination often starts returning 403 after ~10 pages. Get the negative reviews early via rating filters or search.
- Watch for **incentivised review clusters** — badges like "Fair Incentive" or a burst of reviews in one month from a product-trial campaign. These skew positive and gush-y; weight them below organic verified purchases, and say so in your caveats.

**Reddit**
- Direct reddit.com fetches are frequently blocked. Try `old.reddit.com`, a browser tool, or a search-index archive (e.g. pullpush.io) as fallbacks; site-limited web search (`site:reddit.com "{brand}"`) also surfaces threads whose snippets carry usable quotes.
- The most valuable Reddit material is usually NOT dedicated review threads — it's drive-by mentions in condition/problem threads ("what worked for your X?"). Search the brand name, but also search the problem category.
- Reddit is where the skeptics live. Capture the skepticism verbatim — the exact objections ("does this even work / is it placebo / the science says...") are what your landing page has to answer. Don't sanitise it out.

**Brand's own site**
- Usually the largest review corpus and the most positive-skewed (some brands gate or filter). Use it for: total counts, star distribution, featured-quote style, and the brand's own claims to verify. Don't let it dominate theme ranking — it lacks the negative tail.

**Editorial / blog roundups**
- Useful for competitive positioning (who else is recommended, at what price) and for expert framing. But beware: statistics in roundups are often supplied by the brand's PR ("X% of users report..."). Treat as brand-supplied unless independently sourced.

**Amazon (if the brand sells there)**
- Sort by "most recent" AND read the critical-review filter. Amazon's negative reviews skew heavily toward fulfilment issues — separate those from product complaints.

## Sampling traps

1. **Positive-skew default.** Every platform surfaces positive reviews first. If you only read the default sort, you'll write a puff piece. Deliberately seek out the complete 1-3 star corpus.
2. **Recency vs history.** Products change. Note review dates; a complaint cluster from 3 years ago may be fixed. Prefer the last 12-24 months for frequency estimates, use older reviews for durable themes.
3. **One platform ≠ the market.** Trustpilot attracts service complaints; product platforms attract product feedback; Reddit attracts skeptics. Three sources minimum before ranking themes.
4. **Quote truncation.** Search snippets truncate. Mark truncations honestly; never reconstruct or "complete" a quote.
5. **Small-N humility.** If you read 40 reviews, say "~40 reviews read" and present frequencies as rough. Never imply a census you didn't do.

## What to capture per review (mental checklist)

- Verbatim key phrases (the exact words a customer would type into Google)
- The problem they were trying to solve, in their words
- What they tried before (competitors, substitutes, "nothing worked")
- Who they are (any demographic/situation signal)
- The proof device they offer (timeline, measurement, before/after, "removal test")
- For negatives: was the failure product, expectation, or operations?
