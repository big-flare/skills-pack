# Title writing guide

Read this in full before writing the first batch. It is the method: how a Google Shopping title is built, where each kind of word goes, and how to check a title before saving it.

## Why titles matter so much

In Google Shopping there are no keywords to bid on. Google decides which searches a product shows for mostly from its title. A word that isn't in the title is a search the product will struggle to show for. Most store titles are written for people browsing a website ("The Summit 45"), not for the way people search ("45l hiking backpack"), and they use 40 to 60 of the 150 characters Google allows. The gap between the two is the opportunity.

Shoppers usually see only the first 70 or so characters, but Google reads all 150 when it matches searches. So the front of the title has to make sense to a person, and the whole title has to carry search language.

## The shape of a title

A title is a short run of sections separated by `|`. Each section is a phrase someone might actually type into Google. A title has between 3 and 8 sections, depending on the product.

Front to back:

1. **First section:** what the product is, in the words people search, with the single most important search phrase in exact word order. Searched variants can sit here (see Variants). If the store resells other brands, the product's brand goes here or in the second section at the latest.
2. **Next sections:** more search phrases for this product type, highest priority first, in exact word order where they matter most.
3. **Middle (roughly 50 to 65% of the way through):** variant details that buyers want to know but don't type into Google, such as `200ml`, `Pack of 3` or `1 Bottle`, as their own small section.
4. **Later sections:** broader category phrases.
5. **Last section:** the brand name, when the run has one (see Brand). Always last.

Target **130 to 150 characters**. 150 is a hard limit: Google cuts anything longer, and with the brand at the end, the brand is what gets cut. Never trust a length you counted by eye. Use the helper script's `add` and `check` output, or count with code.

## Where the words come from

Start with common sense. A few search phrases are obvious from the product itself: a cast iron skillet will be searched as "cast iron skillet". Then use the research to rank and widen the phrasing. Never rely on research alone, and never skip the obvious phrase because a tool didn't return it.

Sources, strongest first:

1. **The store's own search terms** (from Google Ads). These are the exact words shoppers typed before they saw the products. A phrase with impressions and clicks here has been proven.
2. **Keyword Planner ideas.** Search volume for phrases the store may not show for yet.
3. **The store's website.** How the store and its customers describe the product: materials, uses, who it's for. Facts and phrasing found on other sites through web search (retailers, reviews) are weaker; record them as `web_search`.
4. **The product data.** Product type, attributes and the current title often hold phrases worth keeping.
5. **Your own keyword ideas.** Use these to fill gaps, and only when they are plainly how people would search. They carry no evidence, so they come last.

When the run has no search term data, say so in the delivery and lean harder on sources 2 to 4. Don't present guesses as search data.

Record the phrases each title targets in the draft's `keywords` list, each with its true source. The review page and workbook show them, so the user can see why each phrase is there.

## Three kinds of keyword, in priority order

1. **Product keywords:** searches for this exact product type ("burr coffee grinder"). These go in first.
2. **Category keywords:** broader searches for the category ("coffee bean mill", "espresso equipment"). These fill space once the product keywords are covered.
3. **Use-case keywords:** how people use it ("coffee grinder for french press"). Only when search volume supports them, or when space remains after the first two.

## Pack the most search language into the fewest characters

- **One section can cover several searches.** `Best Coffee Grinder for Espresso & French Press` covers "best coffee grinder", "coffee grinder for espresso" and "coffee grinder for french press" at once.
- **Merge sections that overlap.** If two candidate sections share most of their words, such as "Coffee Grinder for Espresso" and "Best Espresso Coffee Grinder", combine them into one that covers both: "Best Coffee Grinder for Espresso". Prefer the phrasing with more searches.
- **Never repeat a phrase** that already appears elsewhere in the title in exact word order. Repetition wastes space.
- **Spend the space you save** on more product keywords first, then category keywords.
- The most important phrases go in **exact word order**. Lower-priority phrases can be covered by having their words present, not necessarily in order.
- **Cut specs nobody searches.** Before keeping a technical spec (a thickness, a material grade, a model code), check it against the search data. If nobody types it, delete it and use the characters for phrases people do search. A spec earns its place only when buyers search it (a mattress size, a screen size, a pack count when the count is searched).
- **"Best" and similar words** go in only when people actually search them (the search terms or Keyword Planner show "best coffee grinder"). Otherwise they are just promotion, which Google doesn't allow.

## Brand

There are two different brands, and they are handled differently.

- **The store's own brand.** When the store sells its own products, the brand ends every title, in the last section. Brand searchers find the product anyway. People who don't know the brand yet search for the product, so the front of the title is kept for their words. A title that starts with the brand wastes its most valuable space.
- **A brand the store resells.** When the store sells other makers' products, each product's brand goes in the **first half** of its title, next to what the product is: people search "corvane backpack". Leaving it out means brand searches won't match.

In the reseller case the store's own name still ends every title, in the last section, as it does for an own-brand store. Google's title page says not to add "your company's name", so a user who would rather follow that strictly can leave the store name off (`--no-end-brand`); mention the choice once, in the settings line, and don't ask about it unless the user raises it.

The helper script works out which case applies from the feed's brand values and tells you which name (if any) ends the titles. State it to the user in one line.

## Variants

Google asks for each variant's distinguishing details (colour, size, material and so on) to be in its title. Where they go depends on whether people search them:

- **Searched variants** go at the front, inside the product phrase: size ("queen mattress", "10mm yoga mat"), material ("oak bed frame"), colour ("green yoga mat"). Write `Extra Thick Yoga Mat - 10mm - Sage Green`, not `Extra Thick Yoga Mat | 10mm | Sage Green`.
- **Variant details nobody searches** (volume, count, bottle number) go in the middle as their own small section. Never spend front-of-title space on them.
- **Copy variant values exactly** from the original title or the product's attributes. Never guess, swap or invent one. If the original says "Slate Blue", the new title says "Slate Blue". Common colour names help searchers ("green" rather than "emerald"), but only add one alongside the exact value, never instead of it.
- **One template per variant group.** Products that share a base product get the same title structure with only the variant swapped. It keeps titles consistent and guarantees each one is unique.
- **Every title must be unique.** If two products would get the same title, use whatever makes them different in their own data.

## What never goes in a title

From Google's rules (details in `merchant-center-rules.md`): prices, sales, discounts, shipping or delivery, dates and other time-related text ("new for 2026", "this season"), exclamation marks, capitals used for emphasis, emoji and decorative symbols, links, and HTML. Use the store's own capitalisation for brand names and abbreviations ("USB", "LED"). Health claims need care: keep a health-related phrase only if the product's own data supports it.

Numbers come only from the product's data: sizes, counts, volumes. Never add a number the data doesn't contain.

## Examples

These stores and products are invented. The structure is what matters.

**Own brand, with a non-searched pack size in the middle** (store: Woolly Trail):

`Merino Wool Hiking Socks | Cushioned Walking Socks for Men & Women | Thermal Boot Socks | Pack of 3 | Breathable Trail Running Socks | Woolly Trail`

The first section is the main search phrase and nothing else. "Pack of 3" is something buyers want to know but don't search, so it sits about 60% of the way in. The brand is last.

**Own brand, with merged sections** (store: Kettlewick):

`Burr Coffee Grinder | Best Electric Coffee Grinder for Espresso & French Press | Conical Burr Grinder for Home | Coffee Bean Mill | Kettlewick`

The second section covers "best coffee grinder", "electric coffee grinder", "coffee grinder for espresso" and "coffee grinder for french press" in one phrase. "Best" is there because people search "best coffee grinder". "Coffee Bean Mill" is a category phrase, added once the product phrases were covered.

**Searched variants at the front** (store: Loma Studio):

`Extra Thick Yoga Mat - 10mm - Sage Green | Non Slip Exercise Mat for Home Workouts | Pilates Mat with Carry Strap | Gym & Fitness Mat | Loma Studio`

People search "10mm yoga mat" and "green yoga mat", so the thickness and colour sit in the first section, inside the product phrase.

**A brand the store resells** (store: a retailer; product brand: Corvane):

`Corvane Summit 45L Hiking Backpack - Slate Blue | Lightweight Trekking Rucksack | Waterproof Daypack with Rain Cover | Trailhead Supply`

The product's brand is in the first section, next to what the product is. The searched capacity "45L" stays at the front. The retailer's own name, Trailhead Supply, ends the title.

**A variant group with one template** (store: Tidewell):

`Insulated Water Bottle - 750ml - Sage | Stainless Steel Drinks Bottle | Leak Proof Sports Bottle for Gym & Hiking | Reusable Bottle | Tidewell`

`Insulated Water Bottle - 500ml - Charcoal | Stainless Steel Drinks Bottle | Leak Proof Sports Bottle for Gym & Hiking | Reusable Bottle | Tidewell`

Same structure, only the size and colour swapped, both copied exactly from the product data. People search "750ml water bottle", so the size sits at the front.

## Self-check before saving each title

- Is the first section what the product is, in the words people search?
- Is every phrase earning its place: searched, or plainly how people would search?
- Are overlapping phrases merged, with nothing repeated in exact word order?
- Are the variant values present and copied exactly? Is non-searched detail in the middle, not the front?
- Brand rule: the store's name last, plus the resold brand in the first half when the store resells other brands?
- 130 to 150 characters, measured with code, not by eye?
- Nothing promotional, no prices, dates, capitals for emphasis, or numbers that aren't in the data?
- Does it still read as a sensible product name to a person who sees only the first 70 characters?

## Draft record

Save each title as one JSON object:

```json
{
  "id": "SKU-1001",
  "status": "ready",
  "title": "Extra Thick Yoga Mat - 10mm - Sage Green | Non Slip Exercise Mat for Home Workouts | Pilates Mat with Carry Strap | Gym & Fitness Mat | Loma Studio",
  "keywords": [
    {"keyword": "extra thick yoga mat", "source": "search_terms"},
    {"keyword": "10mm yoga mat", "source": "keyword_planner"},
    {"keyword": "non slip exercise mat", "source": "search_terms"},
    {"keyword": "pilates mat", "source": "website"}
  ],
  "notes": ""
}
```

- `status`: `ready`, or `hold` when the product can't be titled safely (for example, the data contradicts itself about what the product is). A held product needs `notes` saying why, and it stays out of the feed file.
- `keywords`: the phrases the title targets, each with its source: `search_terms`, `keyword_planner`, `website` (the store's own site), `web_search` (other sites), `product_data` or `ai` (your own ideas, with no data behind them).
- `notes` (optional): anything the user should know about this title, including why you kept a title the check warned about. Notes show in the workbook and on the review page.
- `thin_data: true` (optional): the product data is too thin to reach 130 characters honestly. The length warning then relaxes; never pad a title with filler to hit the target.
