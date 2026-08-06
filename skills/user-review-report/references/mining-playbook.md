# Review Mining Playbook

Per-platform access quirks and sampling traps, learned the hard way. Read before mining.

Also in here: **"Harvesting ads from the Google Ads Transparency Center"** (last section) — the procedure for Step 1's path 3, used when you need a brand's live ad copy and can't get it from an account or an export.

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
- **Tool-assisted page reading:** if your fetch tool extracts/answers over the page rather than returning raw HTML, quotes it returns still count as "read" — but disclose the mechanism in your caveats, and prefer prompting it to "return the review texts verbatim" over asking for summaries.

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

## Harvesting ads from the Google Ads Transparency Center

This is **Step 1 path 3** — how to get a brand's live ad copy from public data when there's no connected Google Ads account and no user-supplied export. It is the only route that works for a **competitor**, since you will never have their account or their CSV.

`adstransparency.google.com` is Google's own public disclosure tool: no login, no paid tool, no CAPTCHA in normal use. **It requires a browser-automation tool** that can navigate, screenshot and scroll. Without one, this path is unavailable — degrade to path 4 and say so.

### Procedure

1. **Open** `https://adstransparency.google.com/?region=XX&hl=en` (`region` = the two-letter market code; `hl=en` forces English regardless of where you appear to be browsing from).
2. **Resolve the advertiser.** Type the brand into the search box and take the suggestion from the autocomplete dropdown. Two traps: pick the **verified** entity, and note that one brand often has **several entities across regions** with wildly different ad counts (e.g. a US entity with ~1K ads and an EU entity with ~1). Choose the one matching the user's stated market; if another region is far larger, note the imbalance rather than silently switching.
3. **Isolate search ads.** On the advertiser page, append **`&format=TEXT`** to the URL — it is a genuine URL parameter, so use it rather than clicking the filter. The resulting URL looks like:
   `https://adstransparency.google.com/advertiser/AR<id>?region=US&hl=en&format=TEXT`
   The ad count updates to text ads only (e.g. ~1K all formats → ~600 text).
4. **Set a tall viewport** — 1500×2000 fits roughly 12 ads per capture. Worth doing; it cuts the number of cycles by several times.
5. **Capture and read.** Screenshot, read the rendered ads (headline, description, display path, plus any sitelinks, promo extensions and star ratings), scroll, repeat. Record each ad's headline, description and landing path.
6. **Stop** at ~150 ads, or after 3 consecutive captures that yield no new unique headline — whichever comes first. Then report coverage honestly and offer to go deeper.
7. **Save the inventory** to a dated working file so re-runs and follow-ups don't re-scrape.

### Practical harvesting realities

- **Results re-order between page loads.** A fresh load of the same advertiser returns the ads in a different sequence, so you cannot rely on position to track progress. **Dedupe by headline text**, not by index, and expect to re-see ads you already have.
- **Sustained scrolling is where browser tools get flaky.** Long harvests tend to degrade: scroll actions time out, and captures come back blank or mid-repaint. Two mitigations that work: scroll using the browser tool's own scroll action (page-level JS scrolling often does **not** move what the screenshot captures), and reload the advertiser page to reset when captures start coming back empty. If the tool keeps failing, **stop and report the coverage you actually achieved** — a partial harvest honestly labelled is a valid result; a stalled loop is not.
- **Budget realistically.** ~12 ads per capture means a 150-ad harvest is a dozen-plus successful cycles, and a full multi-hundred corpus is many times that. This is the single most expensive step in the skill — which is why the default stop exists.

### Do not waste time on these — both were tried and both fail

- **DOM extraction / `contentDocument`.** The creatives render inside **sandboxed iframes**. Reading `iframe.contentDocument` throws a `SecurityError` even though the frames appear same-origin. `read_page`-style accessibility trees also come back empty on this SPA.
- **Mining the preview bundle.** The iframes load `displayads-formats.googleusercontent.com/ads/preview/content.js`. It fetches fine (200, ~150KB) but the ad copy is **obfuscated inside minified JS** — string-literal extraction returns only library error messages. The URL also carries signed `sig`/`nonce` params minted by the page, so it can't be constructed independently.

**Reading the rendered pixels is the only reliable route.** Go straight to screenshots.

### What this source cannot tell you

- **No performance labels.** LOW/GOOD/BEST asset ratings exist only inside the advertiser's own account. The label cross-reference in Step 4's gap analysis is simply unavailable here — don't imply otherwise.
- **No RSA asset pools.** You see assembled ads as served, not the underlying headline/description pool they were combined from.
- **Frequency means something different.** Counting here is "how many captured creatives displayed this line", NOT "how many ads use this asset". Phrase findings as **"appears across N of the ads we captured"**. Getting this wrong overstates the claim.
- **Currently-running ads only** — no history, no spend, no impressions.

### Hard walls and etiquette

The general rules at the top of this playbook apply unchanged: **never sign in, never bypass a bot check or CAPTCHA, back off on 429 and disclose.** Rate limiting has not been observed at small scale, but has not been tested across a full multi-hundred-ad corpus either — if it appears, stop, report what you captured, and treat the partial harvest as your coverage number.

**Scope guard:** harvest only the brand whose reviews you're analysing. This exists to feed the gap table, not to become a general competitor ad-lookup tool.

### Durability warning

This procedure reads an undocumented third-party UI. When Google changes it, the specifics above (the `format=TEXT` param, autocomplete resolution, the viewport trick) may break. If they do: **degrade to path 4 and tell the user the source is unavailable** — never fail the whole run over it, and never start guessing ad copy.
