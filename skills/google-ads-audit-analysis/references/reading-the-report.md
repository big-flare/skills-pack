# Reading the report

What to look for on each tab, so the summary you give the user points at real opportunities. Every point you make must rest on a number in the workbook or `summary.json`. When something needs a check the data can't do (a tracking change, a stock problem, a price change), say it is a question to ask, not a finding.

Work through the tabs in this order. It goes from the whole account down to single products and searches.

## 1. Account: is the drop real, and where did it start?

- Compare this year with the same months last year (the Start Here tab gives the complete-month comparison). A fall in conv. value with steady cost is a different problem from a fall in both.
- Find the month the trend changed. A sharp break in one month usually has one cause: a tracking change, a campaign change, a site or stock issue, a promotion that ended. A slow slide usually means demand or competition.
- **Search impression share** and its two lost columns: lost to rank means bids, budgets, quality or ROAS targets are holding the account back; lost to budget means it runs out of money. Rising lost-to-budget share while ROAS stays healthy is the clearest sign there is room to spend more.
- **Gross profit after ad spend** is the number that matters to the business. ROAS can rise while profit falls (spend cut too far), or fall while profit rises (more volume at a lower, still profitable ROAS).
- Use the "by conv. time" columns for the latest one or two months: click-time conv. value is still filling in for recent clicks.

## 2. Search Volume: is it the market or the account?

- If searches for the main category keywords fell by about as much as the account's sales, the market shrank and cutting campaigns won't bring sales back. If searches held up and sales fell, the cause is in the account or the site.
- Eligible impressions also move when campaigns start, stop or change targeting, so treat them as a check on the account's reach, not a measure of demand.
- Keyword Planner rounds volumes, so trust the trend over several months more than any single month.

## 3. Channel Split: where Performance Max spend really goes

- **Shopping ads' share of PMax + Shopping spend.** For an ecommerce account, Shopping is usually where the profitable sales are. A large share going to YouTube, Display (Google Display Network), Gmail or Discover is worth questioning when those channels' ROAS is well below Shopping's.
- Compare ROAS by channel, not just cost. A channel with a small share of spend and a weak ROAS is less urgent than a big one.
- Switch the filter to **PMax only** to see Performance Max without standard Shopping, and to **Whole Account** to see every campaign type by the same channels.
- Many asset groups with heavy video and image spend and weak returns often point to a Performance Max campaign that could be run as a Shopping-focused one (for example a feed-only asset group, with no text, images or video). Put that to the user as an option to test, not a rule.

## 4. Campaign and Assets

- On the Campaign tab, find campaigns whose channel mix differs from the rest: one PMax campaign spending most of its budget on video is a different story from one that is nearly all Shopping.
- On the Assets tab, compare assets of the same type. Asset numbers overlap (several assets serve in one ad), so read them as relative: which headlines and images get the impressions, and which earn conversions. Assets with no impressions at all are not being used by Google.

## 5. Products and Product Families: where to cut, where to push

- **Costly** (spend at or above the cost threshold, ROAS below the target): the products losing money or close to it. Check price, stock, reviews and landing page before cutting; then lower their bids, move them to a lower-priority campaign, or exclude them.
- **Profitable**: the products to push. If impression share is lost to budget or the ROAS is far above target, there is likely room for more spend.
- **Low spend**: products Google barely shows. Those with a strong ROAS on their small spend (`low_spend_with_best_roas` in `summary.json`) are the best candidates for their own campaign or a better title and product type.
- **Zombies**: listed products with no spend at all. Often a feed problem (titles, product types, disapprovals) or products Google doesn't trust yet. A large Zombie share means a large part of the catalogue isn't working.
- The **Product Families** tab often tells a different story: a family can be profitable overall while one size or colour is Costly. Look at both.
- Change the thresholds and margin in the cream cells to see how the buckets move.

## 6. Keyword Gap: searches to capture on purpose

- **Missing keyword**: Performance Max is converting on a search the account has no Search keyword for. Adding the best ones as exact match keywords in a Search campaign gives control over the bid, ad and landing page.
- **Not eligible**: a keyword exists but can't show (paused, removed, limited, or in a paused campaign or ad group). These are the quickest fixes.
- Start with the terms with the most conversions. Brand terms usually belong in a brand campaign.

## Writing the summary

Lead with the one finding that matters most, then two to four more, each with its number and its tab. End with what to look at next. Keep it short: the workbook holds the detail.
