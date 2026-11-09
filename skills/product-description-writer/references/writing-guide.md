# Writing guide

How to write one product's description. Read it in full before the first batch. The examples use a fictional brand.

## The recipe

1. **Open with the exact product and its variant.** The first sentence names the product as the title does and the variant that this row is: "Meet the Tidewell Insulated Bottle in Sage, 750 ml, …". Every variant gets its own text, so a shopper looking at the Slate 500 ml never reads a description written for a different size. "Meet the …" is a strong opener; vary it when a run has many products, but keep the product and variant in the first sentence.
2. **Four or five full sentences, about 600 to 750 characters.** Real sentences with full stops, not a stripped bullet list. Put the facts a shopper decides on (what it is, the variant, the key feature, the main material or spec) in the first 160 to 500 characters, because that is what Shopping shows before a click.
3. **Only the product's own data.** Title, product highlights, product details, product type, attributes (colour, size, material and so on), the original description, and product-page facts if the user turned that on. Nothing from general knowledge about the category, nothing about competitors, nothing guessed.
4. **Keep every fact from the original.** The new text replaces the old one, so a fact that is missing from the new text is lost from Shopping. The only things that leave are the ones listed under "Leave out" below; record each one in `left_out` with a reason.
5. **Benefits only when the data states them.** If a highlight says "the lid is leak-proof", you can say the lid is leak-proof. You cannot add "so your bag stays dry" unless the data says that. A benefit you work out yourself is an invented claim. Watch for small tacked-on purpose phrases, the easiest invention to miss: "packs into its own pocket **for easy travel**", "**ideal for** everyday wear". Each one needs to be in the data. Paraphrase without changing the meaning, and do not reinterpret a brand slogan into a new claim ("summit to street" does not become "for hiking and everyday wear"): keep the slogan's own words or leave it out.
6. **Use the searchable words that are already in the data.** Category and feature words from the title, product type and highlights ("insulated water bottle", "stainless steel", "merino", "waterproof") should appear naturally, once or twice. Do not add keywords the data does not contain, and do not repeat words to stuff them in.
7. **Plain, professional sentences.** One idea per sentence. No exclamation marks, no emoji, no capitals for emphasis, no hype.

## The fact sheet (do this first, every product)

Before writing, list the product's facts in your working notes, each with its source:

```
Tidewell Insulated Bottle, Sage, 750 ml  [title, color, size]
double-wall vacuum insulation             [highlight 1, original]
18/8 stainless steel                      [original]
keeps hot drinks hot 12 hours             [highlight 2, original]
keeps cold drinks cold 24 hours           [highlight 2]   CONFLICT: product page says "up to 18 hours"
leak-proof screw lid with carry loop      [highlight 3]
powder-coated finish resists scratches    [product page]
lid dishwasher safe; hand-wash the bottle [highlight 4]
"Free shipping on orders over $50"        [original]      LEAVE OUT: shipping/promo
```

Write only from this list. Then tick each fact off against the draft before you save it.

## Variants

- Products that share an `item_group_id` are variants of one product. If there is no `item_group_id` but several products share the same original description and differ by colour or size (or by the end of the title), treat them as variants too: the script marks these as an implicit group.
- Each variant's description names its own values (`variant_parts` in the product record): colour, size, material, pattern, whatever differs. The check fails any variant whose description does not name them.
- Variants can share most of their sentences. The opener must differ, and any fact that only applies to some variants (a dimension, a capacity, a fit note) must only appear in those variants' text.
- Size letters: write them so a shopper understands them ("size M" or "in Medium"), not as a bare "M".

## Conflicts: when the sources disagree

A conflict is two sources stating different values for the same fact: the product page says "recycled nylon" and the highlights say "recycled polyester"; a highlight says "24 hours" and the page says "up to 18 hours"; the title says "Linen" and the material attribute says "Cotton".

- **Leave the fact out of the copy.** Do not pick a side, do not average, do not hedge with "up to".
- **Record it** in `conflicts` with what each source says, so the review page can ask a human to decide.
- If the conflict is about the variant's identity itself (the title says Red, the colour attribute says Blue), set the draft to `"status": "hold"` with a note. A wrong variant name is worse than no new description.
- Missing information is not a conflict. If only one source states a fact and nothing contradicts it, use it.

## Leave out (and record in `left_out`)

- Prices, sale prices, discounts, coupons, "free shipping", delivery times, and store-wide returns or money-back policies.
- Not this: a warranty, guarantee or trial period that the product's own data states ("100-night trial", "10-year warranty") is a fact about what the buyer gets, so keep it, written plainly (usually as the last sentence). Don't add "risk-free" or "money-back" framing that the data doesn't contain.
- Time-related and promotional lines: "new for this season", "limited edition", "bestseller", "back in stock", "while stocks last".
- The store's or company's name used as promotion ("Shop the full range at …"). The product's own brand name is fine.
- Links, web addresses, email addresses, phone numbers.
- Comparisons with other products or brands.
- Category paths ("Home > Kitchen > Bottles").
- Health or medical claims, even when the original contains them: anything about treating, curing, relieving, preventing or improving a condition, pain, immunity, energy or wellbeing. A plain material spec that the data states (for example "antimicrobial-treated lining") can stay; a health benefit built on it cannot. Record health claims you leave out so the user can decide whether they can substantiate them.
- Superlatives and hype the data does not contain: best, perfect, ultimate, premium, luxury, world-class, amazing. If the data itself uses one (a product named "Ultimate Hoodie"), the name stays; do not add more.
- Anything about other products, accessories or bundles that this item is not.

## Thin data

Some products have little more than a title. Do not pad. Write two or three accurate sentences from what exists, set `"thin_data": true`, and say in `notes` which data would make the description better (highlights, material, dimensions). A short true description beats a long invented one.

## Language and spelling

Write in the run's language (`language` in `run-config.json`, worked out from the feed in Step 3), with that market's spelling (colour/color, grey/gray, aluminium/aluminum, litre/liter). Proper names in the data keep their spelling ("Heather Gray" stays "Heather Gray" in a British feed if that is the colour name). Keep units as the data gives them; do not convert.

## Format rules for the text itself

- Plain text only: no HTML, no line breaks, no tabs, no bullet symbols.
- Do not start the text with a double quote mark.
- Under 5,000 characters (the check flags anything outside 500 to 900 as worth a look).
- Every number in the text must appear in the product's data. The check fails a draft that contains a number the data does not.

## The draft record

Save each product's result as one JSON object:

```json
{
  "id": "TW-INS-750-SAGE",
  "status": "ready",
  "description": "Meet the Tidewell Insulated Bottle in Sage, 750 ml, ...",
  "conflicts": [
    {"fact": "cold-drink duration",
     "sources": [{"source": "product_highlight", "says": "cold for 24 hours"},
                 {"source": "product page", "says": "cold for up to 18 hours"}]}
  ],
  "left_out": [{"text": "Free shipping on orders over $50", "reason": "shipping/promotional"}],
  "page": {"url": "https://example.com/products/tidewell-bottle", "status": "read",
           "facts": ["Powder-coated finish resists scratches", "Keeps drinks cold for up to 18 hours"]},
  "thin_data": false,
  "notes": ""
}
```

- `status`: `ready` (goes into the feed file) or `hold` (left out of the feed file, explained in `notes`).
- `page`: only when product pages are being read; `status` is `read`, `failed` or `skipped`. List the product facts you took from the page in `facts`, in close to the page's own words (not your summary or interpretation): they count as the product's data for the number check, and a human may check them against the page.
- `conflicts`, `left_out`, `thin_data`, `notes`: include when they apply.

## Worked example (fictional)

**Product data**

- id `TW-INS-750-SAGE`, item_group_id `TW-INS`
- title: Tidewell Insulated Bottle 750 ml - Sage
- color: Sage; size: 750 ml; material: Stainless steel
- product_type: Kitchen & Dining > Drinkware > Water Bottles
- product_highlight: "Double-wall vacuum insulation" / "Keeps drinks hot for 12 hours and cold for 24 hours" / "Leak-proof screw lid with carry loop" / "Lid is dishwasher safe; hand-wash the bottle"
- original description (as Google receives it, stripped of HTML): `Double-wall vacuum insulation Keeps drinks hot 12 hours 18/8 stainless steel Leak-proof screw lid Powder-coated finish Free shipping on orders over $50`
- product page: "Powder-coated finish resists scratches." / "Keeps drinks cold for up to 18 hours."

**Weak rewrite (what not to do)**

> The best water bottle you'll ever own! Stay hydrated and energised all day with our premium bottle that keeps drinks ice cold for 24 hours. Perfect for the gym, the office and every adventure. Free shipping over $50.

Problems: superlatives not in the data (best, premium, perfect), a health/wellbeing claim (hydrated and energised), a conflicting fact stated as true (24 hours), invented uses (gym, office, adventure), shipping text, an exclamation mark, and the variant is never named.

**Good rewrite**

> Meet the Tidewell Insulated Bottle in Sage, a 750 ml stainless steel water bottle with double-wall vacuum insulation. It is made from 18/8 stainless steel and keeps hot drinks hot for 12 hours. The leak-proof screw lid has a built-in carry loop. The powder-coated Sage finish resists scratches. The lid can go in the dishwasher, while the bottle itself should be washed by hand.

Every fact is in the data. The cold-drink claim is left out and recorded as a conflict; the shipping line is recorded in `left_out`. It runs to about 400 characters because that is all the data supports: better than padding it to 650.

**The Slate 500 ml variant** opens differently ("Meet the Tidewell Insulated Bottle in Slate, a 500 ml stainless steel water bottle …") and only mentions a size-specific fact (for example "fits most car cup holders") if that variant's own data says so.

## Self-check before saving each batch

- Does the first sentence name the exact product and this variant?
- Is every fact in the text on the fact sheet, and every fact on the fact sheet either in the text or recorded as left out or conflicting?
- Any number, claim, benefit or purpose phrase ("for easy travel", "ideal for …") that is not in the data? Remove it.
- Any price, shipping, delivery or returns policy, promotion, link, comparison, health claim, hype word, exclamation mark or emoji? Remove it. (A warranty or trial period stated in the product's data stays.)
- Is it four or five full sentences in the run's language and spelling?
