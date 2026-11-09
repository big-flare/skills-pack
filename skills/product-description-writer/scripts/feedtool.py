#!/usr/bin/env python3
"""feedtool.py - helper script for the product-description-writer skill (Big Flare Skills Pack).

Python 3.8+, standard library only. Nothing to install.

It does the mechanical work so the writing can focus on the copy:

  inspect   FEED                              Summarise a feed: columns, likely ID column, variants,
                                              what is wrong with the current descriptions, language and spelling.
  normalise FEED --run DIR                    Turn the chosen products into one record shape
            (--pick ITEM ... | --pick-file F | --first N | --all)
            [--store NAME] [--no-variants] [--force]
            [--id-col COL] [--lang en-GB]       Overrides only: both are worked out from the feed.
  next      --run DIR [--batch 10]            Print the next products that have no draft yet (resume-safe).
  add       --run DIR BATCH.json              Validate drafts and save them to DIR/drafts.jsonl
                                              (a draft for an ID that already has one replaces it).
  check     --run DIR                         Lint every draft against the writing rules.
  build     --run DIR [--force]               Write the supplemental feed (.tsv) and the review page (.html).

Accepted feed files: Google Shopping XML (RSS 2.0 or Atom with g: tags), delimited text
(.tsv/.txt/.csv - tab, comma, semicolon or pipe), and .xlsx (first sheet).
"""

import argparse
import csv
import datetime
import hashlib
import html
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "references", "review-template.html")

# ---------------------------------------------------------------------------
# Attribute vocabulary
# ---------------------------------------------------------------------------

ALIASES = {
    "colour": "color",
    "product_highlights": "product_highlight",
    "highlights": "product_highlight",
    "highlight": "product_highlight",
    "product_details": "product_detail",
    "body_html": "description",
    "item_group": "item_group_id",
    "itemgroupid": "item_group_id",
    "group_id": "item_group_id",
    "producttype": "product_type",
    "googleproductcategory": "google_product_category",
    "google_category": "google_product_category",
}

LIST_ATTRS = {"product_highlight", "product_detail", "additional_image_link", "product_type"}

# Attributes that can distinguish one variant from another.
VARIANT_KEYS = ["color", "size", "material", "pattern", "age_group", "gender",
                "size_type", "size_system", "flavor", "flavour", "scent", "style", "capacity"]

# Attributes that are product facts the writer may use.
FACT_ATTRS = ["brand", "color", "size", "material", "pattern", "age_group", "gender",
              "size_type", "size_system", "condition", "multipack", "is_bundle",
              "product_length", "product_width", "product_height", "product_weight",
              "unit_pricing_measure", "energy_efficiency_class", "certification",
              "flavor", "flavour", "scent", "style", "capacity"]

# Columns that are never product facts for a description (prices, logistics, ad plumbing).
DROP_PREFIXES = ("price", "sale_price", "shipping", "tax", "availability", "image_link",
                 "additional_image_link", "mobile_link", "custom_label", "promotion",
                 "ads_", "adwords", "excluded_destination", "included_destination",
                 "shopping_ads", "pause", "expiration", "cost_of_goods", "installment",
                 "subscription", "loyalty", "store_code", "pickup", "return", "min_handling",
                 "max_handling", "transit", "lifestyle_image", "canonical_link",
                 "identifier_exists", "gtin", "mpn", "feed_label", "target_country",
                 "content_language", "channel", "item_id", "offer_id", "product_id",
                 "sku", "variant_id", "auto_pricing", "free_shipping", "external_seller",
                 "virtual_model", "disclosure_date", "sell_on_google", "structured_",
                 "short_title", "link_template", "mobile_link_template")

ID_CANDIDATES = ["id", "item_id", "offer_id", "product_id", "sku", "variant_id", "variant_sku", "mpn"]

REST_ID = re.compile(r"^(online|local):[a-z]{2,3}:[A-Za-z]{2}:(.+)$")
MERCHANT_API_ID = re.compile(r"^[a-z]{2,3}~[A-Za-z]{2}~(.+)$")


def norm_key(k):
    k = (k or "").strip().lower()
    if k.startswith("g:"):
        k = k[2:]
    k = re.sub(r"[^a-z0-9]+", "_", k).strip("_")
    m = re.match(r"^(product_highlights?|product_details?|highlights?|additional_image_links?)_?\d+$", k)
    if m:
        k = m.group(1)
    k = ALIASES.get(k, k)
    if k == "additional_image_links":
        k = "additional_image_link"
    return k


# ---------------------------------------------------------------------------
# Reading feeds
# ---------------------------------------------------------------------------

def decode(raw):
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def rows_from_table(table):
    """table: list of lists, first non-empty row is the header. Returns (headers, rows as dict key->list)."""
    table = [r for r in table if any((c or "").strip() for c in r)]
    if not table:
        return [], []
    header = [norm_key(h) for h in table[0]]
    out = []
    for r in table[1:]:
        rec = {}
        for i, key in enumerate(header):
            if not key:
                continue
            val = (r[i] if i < len(r) else "") or ""
            val = val.strip()
            if not val:
                continue
            rec.setdefault(key, []).append(val)
        if rec:
            out.append(rec)
    uniq = []
    for h in header:
        if h and h not in uniq:
            uniq.append(h)
    return uniq, out


def read_delimited(text):
    lines = text.splitlines()
    first = lines[0] if lines else ""
    counts = {d: first.count(d) for d in ["\t", ",", ";", "|"]}
    delim = max(counts, key=counts.get)
    if counts[delim] == 0:
        delim = ","
    table = list(csv.reader(io.StringIO(text), delimiter=delim))
    width = len(table[0]) if table else 0
    bad = sum(1 for r in table[1:] if r and len(r) != width)
    if delim == "\t" and table and bad > max(2, len(table) // 20):
        # Unquoted tab file whose values contain stray quote characters.
        table = list(csv.reader(io.StringIO(text), delimiter=delim, quoting=csv.QUOTE_NONE))
    headers, rows = rows_from_table(table)
    return headers, rows, {"format": "delimited", "delimiter": {"\t": "tab", ",": "comma", ";": "semicolon", "|": "pipe"}[delim]}


def local(tag):
    return tag.split("}", 1)[-1] if isinstance(tag, str) else ""


def read_xml(raw):
    root = ET.fromstring(raw)
    items = [el for el in root.iter() if local(el.tag) in ("item", "entry")]
    rows = []
    headers = []
    for it in items:
        rec_g, rec_p = {}, {}
        for ch in list(it):
            key = norm_key(local(ch.tag))
            is_google = ch.tag.startswith("{http://base.google.com/ns/1.0}")
            kids = list(ch)
            if key == "product_detail" and kids:
                parts = {local(k.tag): (k.text or "").strip() for k in kids}
                val = "%s:%s:%s" % (parts.get("section_name", ""), parts.get("attribute_name", ""), parts.get("attribute_value", ""))
            elif kids:
                val = "; ".join("%s:%s" % (local(k.tag), (k.text or "").strip()) for k in kids if (k.text or "").strip())
            elif key == "link" and ch.get("href"):
                val = ch.get("href")
            else:
                val = (ch.text or "").strip()
            if not val:
                continue
            if key not in headers:
                headers.append(key)
            (rec_g if is_google else rec_p).setdefault(key, []).append(val)
        # g: values first (so g:title wins over a plain <title>), in document order
        rec = {k: rec_g.get(k, []) + rec_p.get(k, []) for k in list(rec_g) + [k for k in rec_p if k not in rec_g]}
        if rec:
            rows.append(rec)
    return headers, rows, {"format": "xml", "items": len(items)}


def col_index(ref):
    letters = re.match(r"[A-Z]+", ref or "A").group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx(path):
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    z = zipfile.ZipFile(path)
    names = z.namelist()
    shared = []
    if "xl/sharedStrings.xml" in names:
        sroot = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in sroot.findall(m + "si"):
            shared.append("".join(t.text or "" for t in si.iter(m + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheet = wb.find(m + "sheets").findall(m + "sheet")[0]
    rid = sheet.get(r + "id")
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = None
    for rel in rels:
        if rel.get("Id") == rid:
            target = rel.get("Target")
    if not target:
        target = "worksheets/sheet1.xml"
    spath = target.lstrip("/") if target.startswith("/") else "xl/" + target
    sh = ET.fromstring(z.read(spath))
    table = []
    for row in sh.iter(m + "row"):
        cells = {}
        for c in row.findall(m + "c"):
            t = c.get("t")
            v = c.find(m + "v")
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(m + "t"))
            else:
                val = v.text if v is not None and v.text is not None else ""
                if t not in ("str", "b") and re.match(r"^-?\d+\.0$", val):
                    val = val[:-2]
            cells[col_index(c.get("r"))] = val
        table.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
    headers, rows = rows_from_table(table)
    return headers, rows, {"format": "xlsx", "sheet": sheet.get("name")}


def load_feed(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"PK":
        return read_xlsx(path)
    head = raw[:500].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith(b"<"):
        return read_xml(raw)
    return read_delimited(decode(raw))


def first(rec, key):
    v = rec.get(key)
    return v[0] if v else ""


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

BLOCK = re.compile(r"(?i)<br\s*/?>|</?(p|li|ul|ol|div|h[1-6]|tr|td|th|section|table)\b[^>]*>")


def html_segments(s):
    """Split an HTML-ish description into text segments at block boundaries."""
    s = html.unescape(s or "")
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = BLOCK.sub("\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    segs = [re.sub(r"\s+", " ", x).strip(" -•·*") for x in s.split("\n")]
    return [x for x in segs if x]


def flat_text(s):
    return " ".join(html_segments(s)).strip()


def has_markup(s):
    return bool(re.search(r"<[a-zA-Z/][^>]*>|&lt;|&gt;", s or ""))


SENT_END = re.compile(r"[.!?][\"')\]]?(\s|$)")


def sentence_count(s):
    return len(SENT_END.findall(s or ""))


def is_run_on(s):
    """True when the text has a stretch of 200+ characters with no full stop (a stripped list)."""
    return any(len(chunk.strip()) >= 200 for chunk in SENT_END.split(s or ""))


PROMO_ORIG = re.compile(r"(?i)\b(free (shipping|delivery|returns?)|shipping|delivery|dispatch|sale|discount|% off|"
                        r"limited[- ](edition|time)|new arrival|best[- ]?sell(er|ing)|order (now|today)|"
                        r"buy now|shop now|in stock|while stocks? last)\b")


def norm_desc(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

EN_GB = ["colour", "grey", "aluminium", "centre", "litre", "favourite", "jewellery", "fibre", "flavour", "cosy"]
EN_US = ["color", "gray", "aluminum", "center", "liter", "favorite", "jewelry", "fiber", "flavor", "cozy"]
LANG_HINTS = {
    "de": ["und", "der", "die", "das", "mit", "für", "ist"],
    "fr": ["et", "le", "la", "les", "avec", "pour", "est"],
    "es": ["y", "el", "la", "los", "con", "para", "es"],
    "nl": ["en", "de", "het", "met", "voor", "is", "een"],
    "it": ["e", "il", "la", "con", "per", "di", "è"],
    "en": ["and", "the", "with", "for", "is", "a", "of"],
}


def guess_language(texts):
    words = re.findall(r"[a-zà-ÿ]+", " ".join(texts).lower())
    if len(words) < 30:
        return {"guess": "unknown - too little text to tell", "evidence": {"words": len(words)}}
    total = len(words)
    scores = {}
    for lang, hints in LANG_HINTS.items():
        hs = set(hints)
        scores[lang] = sum(1 for w in words if w in hs) / total
    lang = max(scores, key=scores.get)
    if scores[lang] < 0.02:
        return {"guess": "unknown - no clear language signal", "evidence": {"words": total}}
    ev = {"function_word_share": {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])[:3]}}
    if lang == "en":
        wl = set(words)
        gb = [w for w in EN_GB if w in wl]
        us = [w for w in EN_US if w in wl]
        ev["gb_spellings_seen"] = gb
        ev["us_spellings_seen"] = us
        if len(gb) > len(us):
            lang = "en-GB (or en-AU/NZ/IE)"
        elif len(us) > len(gb):
            lang = "en-US"
        else:
            lang = "English (spelling market unclear)"
    return {"guess": lang, "evidence": ev}


def common_title_prefix(titles):
    """Longest shared run of whole words at the start of every title."""
    out = []
    for parts in zip(*[t.split() for t in titles]):
        if all(p == parts[0] for p in parts):
            out.append(parts[0])
        else:
            break
    return (" ".join(out) + " ") if out else ""


def build_groups(rows, id_key):
    """Return dict id -> group info (group key, members, variant attrs)."""
    groups = {}
    for r in rows:
        pid = first(r, id_key)
        g = first(r, "item_group_id")
        key = ("g:" + g) if g else None
        if not key:
            d = norm_desc(flat_text(first(r, "description")))
            key = ("d:" + hashlib.md5(d.encode()).hexdigest()[:10]) if d else ("i:" + pid)
        groups.setdefault(key, []).append(r)
    info = {}
    for key, members in groups.items():
        varying = []
        for k in VARIANT_KEYS:
            vals = {first(m, k) for m in members if first(m, k)}
            if len(members) > 1 and len(vals) > 1:
                varying.append(k)
        prefix = common_title_prefix([first(m, "title") for m in members]) if len(members) > 1 else ""
        vo_differs = len(members) > 1 and not varying and len({first(m, "variant_option") for m in members}) > 1
        for m in members:
            pid = first(m, id_key)
            if vo_differs and first(m, "variant_option"):
                # e.g. "color:Red;size:M" -> ["Red", "M"]
                parts = [x.split(":", 1)[-1].strip() for x in re.split(r"[;|,]", first(m, "variant_option")) if x.strip()]
                label = ", ".join(parts)
            elif varying:
                label = ", ".join(first(m, k) for k in varying if first(m, k))
                parts = [first(m, k) for k in varying if first(m, k)]
            elif len(members) > 1 and prefix and key.startswith(("g:", "d:")):
                t = first(m, "title")
                rest = t[len(prefix):] if t.startswith(prefix) else ""
                rest = rest.strip(" -|/,:–—")
                label = rest
                parts = [p.strip() for p in re.split(r"\s*[/|,]\s*", rest) if p.strip()] if rest else []
            else:
                label, parts = "", []
            info[pid] = {"group": key, "group_size": len(members), "variant_attrs": varying,
                         "variant_label": label, "variant_parts": parts,
                         "implicit_group": key.startswith("d:") and len(members) > 1}
    return info


STANDARD_ID_COLS = ["id", "item_id", "offer_id"]
SCI = re.compile(r"^\d+(\.\d+)?[eE]\+?\d+$")


def pick_id_column(headers, rows, override=""):
    """Work out the Merchant Center item ID column instead of asking.

    Uses the feed's standard id column (g:id, id, item id, offer id) unless the user named one.
    Returns column, from_rest (strip online:en:US: prefixes), samples, notes, and problem
    (a reason the file can't be used; None when it can)."""
    out = {"column": None, "from_rest": False, "samples": [], "notes": [], "problem": None}
    if override:
        col = norm_key(override)
        if col not in headers:
            out["problem"] = "Column '%s' not found. Columns: %s" % (override, ", ".join(headers))
            return out
    else:
        col = next((c for c in STANDARD_ID_COLS if c in headers and any(first(r, c) for r in rows)), None)
    if not col:
        others = list(dict.fromkeys(c for c in ID_CANDIDATES + [h for h in headers if h.endswith("_id")] if c in headers))
        out["problem"] = ("This file has no item ID column (id), so it is probably a store export rather than the feed "
                          "Google Merchant Center reads. A supplemental feed built from it would match nothing. Use the "
                          "feed your feed app sends to Merchant Center, or a Merchant Center product download.")
        if others:
            out["problem"] += (" If the user says one of these columns holds the Merchant Center item IDs, rerun with "
                               "--id-col: " + ", ".join(others))
        return out
    filled = [first(r, col) for r in rows if first(r, col)]
    out["column"] = col
    out["samples"] = filled[:3]
    if any(SCI.match(v) for v in filled):
        out["problem"] = ("Some IDs are in scientific notation (like 1.23E+13): a spreadsheet has mangled long numbers, so "
                          "they would not match. Re-export the feed with the ID column formatted as text.")
    if any(REST_ID.match(v) or MERCHANT_API_ID.match(v) for v in filled):
        out["from_rest"] = True
        out["notes"].append("IDs are full Merchant Center product IDs (like online:en:US:ABC123). Only the last part is "
                            "the item ID, so only that goes in the supplemental feed.")
    if len(filled) < len(rows):
        out["notes"].append("%d row(s) have no ID and will be skipped." % (len(rows) - len(filled)))
    if len(set(filled)) < len(filled):
        out["notes"].append("Some IDs appear more than once (the file may hold several countries or languages); "
                            "each ID gets one description.")
    return out


COUNTRY_MARKET = {"GB": "en-GB", "UK": "en-GB", "IE": "en-IE", "AU": "en-AU", "NZ": "en-NZ", "CA": "en-CA",
                  "US": "en-US", "ZA": "en-ZA", "IN": "en-IN", "SG": "en-SG"}
CURRENCY_MARKET = {"GBP": "en-GB", "AUD": "en-AU", "NZD": "en-NZ", "CAD": "en-CA", "USD": "en-US",
                   "ZAR": "en-ZA", "INR": "en-IN", "SGD": "en-SG"}
SYMBOL_MARKET = {"£": "en-GB"}
TLD_MARKET = [(".co.uk", "en-GB"), (".uk", "en-GB"), (".com.au", "en-AU"), (".au", "en-AU"), (".co.nz", "en-NZ"),
              (".nz", "en-NZ"), (".ie", "en-IE"), (".ca", "en-CA"), (".us", "en-US"), (".co.za", "en-ZA"),
              (".in", "en-IN"), (".sg", "en-SG")]
MARKET_NAMES = {"en-GB": "UK", "en-IE": "Irish", "en-AU": "Australian", "en-NZ": "New Zealand", "en-CA": "Canadian",
                "en-US": "US", "en-ZA": "South African", "en-IN": "Indian", "en-SG": "Singapore"}
LANG_NAMES = {"en": "English", "de": "German", "fr": "French", "es": "Spanish", "nl": "Dutch", "it": "Italian"}


def _vote(values):
    counts = {}
    for v in values:
        if v:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return None, 0
    best = max(counts, key=counts.get)
    return best, counts[best]


def detect_language(headers, rows, override=""):
    """Work out the language and spelling market instead of asking.

    Strongest signal first: a content_language / target-country column, then the price currency, then the
    link domains, then the spelling the current copy uses. Returns code (e.g. en-GB, en, de), summary,
    evidence, and confident (False when the spelling market is still open)."""
    if override:
        return {"code": override, "summary": "%s (set by the user)" % override, "evidence": ["set by the user"],
                "confident": True}
    descs = [flat_text(first(r, "description")) for r in rows[:200]]
    text_guess = guess_language(descs + [first(r, "title") for r in rows[:200]])
    ev = []
    lang, _ = _vote([first(r, "content_language").lower()[:2] for r in rows])
    if lang:
        ev.append("content_language column says '%s'" % lang)
    else:
        g = text_guess["guess"]
        lang = "en" if g.startswith(("en", "English")) else (g if g in LANG_HINTS else None)
        if lang:
            ev.append("the feed text reads as %s" % LANG_NAMES.get(lang, lang))
    if not lang:
        return {"code": "", "summary": "language unclear from the feed - check a product page", "evidence": ev,
                "confident": False, "text_evidence": text_guess["evidence"]}
    if lang != "en":
        return {"code": lang, "summary": LANG_NAMES.get(lang, lang), "evidence": ev, "confident": True}
    # English: which spelling market?
    country, n = _vote([COUNTRY_MARKET.get((first(r, "target_country") or first(r, "feed_label")).upper()) for r in rows])
    if country:
        ev.append("target country / feed label points to %s" % country)
    cur_vals = []
    for r in rows:
        pr = first(r, "price") or first(r, "sale_price")
        m = re.search(r"\b([A-Z]{3})\b", pr)
        cur_vals.append(CURRENCY_MARKET.get(m.group(1)) if m else
                        next((v for k, v in SYMBOL_MARKET.items() if k in pr), None))
    currency, _ = _vote(cur_vals)
    if currency:
        ev.append("prices in %s" % next(k for k, v in CURRENCY_MARKET.items() if v == currency))
    tld_vals = []
    for r in rows:
        host = re.sub(r"^https?://", "", first(r, "link").lower()).split("/")[0].split(":")[0]
        tld_vals.append(next((v for t, v in TLD_MARKET if host.endswith(t)), None))
    tld, _ = _vote(tld_vals)
    if tld:
        ev.append("links on %s" % next(t for t, v in TLD_MARKET if v == tld))
    spell = text_guess["guess"]
    spelling = "en-US" if spell == "en-US" else ("en-GB" if spell.startswith("en-GB") else None)
    se = text_guess["evidence"]
    if spelling:
        ev.append("the current copy uses %s spelling (%s)" % ("US" if spelling == "en-US" else "UK",
                  ", ".join((se.get("us_spellings_seen") if spelling == "en-US" else se.get("gb_spellings_seen")) or [])))
    code = country or currency or tld or spelling
    if not code:
        return {"code": "en", "summary": "English (spelling market unclear: check the website, otherwise US spelling)",
                "evidence": ev or ["no country, currency, domain or spelling signal"], "confident": False}
    return {"code": code, "summary": "English, %s spelling" % MARKET_NAMES.get(code, code), "evidence": ev,
            "confident": True}


def cmd_inspect(a):
    headers, rows, meta = load_feed(a.feed)
    out = {"file": os.path.abspath(a.feed), "format": meta, "products": len(rows), "columns": headers}
    if not rows:
        out["problem"] = "No product rows found. Is this the right file?"
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    if "handle" in headers and ("variant_sku" in headers or "option1_name" in headers):
        out["warning_shopify_export"] = ("This looks like a Shopify product export. It does not contain the item IDs "
                                         "Google Merchant Center uses, so a supplemental feed built from it will not match. "
                                         "Use a Merchant Center product download or your feed app's feed instead.")
    cands = []
    for c in ID_CANDIDATES + [h for h in headers if h.endswith("_id") and h not in ID_CANDIDATES]:
        if c in headers:
            vals = [first(r, c) for r in rows]
            filled = [v for v in vals if v]
            uniq = len(set(filled))
            rest_like = sum(1 for v in filled if REST_ID.match(v) or MERCHANT_API_ID.match(v))
            sci = sum(1 for v in filled if re.match(r"^\d+(\.\d+)?[eE]\+?\d+$", v))
            cands.append({"column": c, "filled": len(filled), "unique": uniq, "samples": filled[:3],
                          "looks_like_rest_ids": rest_like > 0, "scientific_notation": sci > 0})
    cands.sort(key=lambda x: (x["column"] != "id", -(x["unique"] == len(rows))))
    out["id_candidates"] = cands
    if cands:
        best = cands[0]
        out["id_recommendation"] = best["column"]
        notes = []
        if best["unique"] < len(rows):
            notes.append("Not every row has a unique value in this column.")
        if best["looks_like_rest_ids"]:
            notes.append("Values look like full Merchant Center REST IDs (e.g. online:en:US:ABC123). The supplemental feed needs "
                         "only the last part (the item ID) - normalise with --id-from-rest.")
        if best["scientific_notation"]:
            notes.append("Some IDs are in scientific notation (a spreadsheet mangled long numbers). Re-export with the ID column as text.")
        out["id_notes"] = notes
    id_key = out.get("id_recommendation", "id")
    ginfo = build_groups(rows, id_key)
    groups = {}
    for v in ginfo.values():
        groups.setdefault(v["group"], v)
    multi = [g for g in groups.values() if g["group_size"] > 1]
    out["variants"] = {
        "has_item_group_id": "item_group_id" in headers,
        "groups_with_2plus_variants": len(multi),
        "products_in_those_groups": sum(g["group_size"] for g in multi),
        "variant_attributes_seen": sorted({k for g in multi for k in g["variant_attrs"]}),
        "groups_found_by_shared_description_only": sum(1 for g in multi if g["implicit_group"]),
    }
    descs = [flat_text(first(r, "description")) for r in rows]
    raws = [first(r, "description") for r in rows]
    counts = {}
    for d in descs:
        if d:
            counts[norm_desc(d)] = counts.get(norm_desc(d), 0) + 1
    lengths = [len(d) for d in descs if d]
    out["descriptions"] = {
        "empty": sum(1 for d in descs if not d),
        "shared_with_another_product": sum(1 for d in descs if d and counts[norm_desc(d)] > 1),
        "contain_html_or_markup": sum(1 for x in raws if has_markup(x)),
        "run_on_200_chars_without_full_stop": sum(1 for d in descs if is_run_on(d)),
        "promotional_or_time_text": sum(1 for d in descs if PROMO_ORIG.search(d)),
        "avg_length": round(sum(lengths) / len(lengths)) if lengths else 0,
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
    }
    out["useful_fact_columns_present"] = [h for h in headers if h in ("title", "description", "product_highlight", "product_detail",
                                                                       "product_type", "google_product_category", "brand") or h in FACT_ATTRS]
    out["has_links"] = sum(1 for r in rows if first(r, "link"))
    out["language"] = detect_language(headers, rows)
    idp = pick_id_column(headers, rows)
    out["item_id"] = {"column": idp["column"], "samples": idp["samples"], "strip_to_item_id": idp["from_rest"],
                      "notes": idp["notes"], "problem": idp["problem"]}
    out["sample_titles"] = [first(r, "title") for r in rows[:5]]
    print(json.dumps(out, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------

def parse_detail(v):
    parts = v.split(":")
    if len(parts) >= 3:
        return {"section": parts[0].strip(), "name": parts[1].strip(), "value": ":".join(parts[2:]).strip()}
    if len(parts) == 2:
        return {"section": "", "name": parts[0].strip(), "value": parts[1].strip()}
    return {"section": "", "name": "", "value": v.strip()}


def product_record(r, id_key, ginfo, shared_counts, id_from_rest):
    raw_id = first(r, id_key)
    pid = raw_id
    if id_from_rest:
        m = REST_ID.match(raw_id) or MERCHANT_API_ID.match(raw_id)
        if m:
            pid = m.groups()[-1]
    desc_raw = first(r, "description")
    desc = flat_text(desc_raw)
    flags = []
    if not desc:
        flags.append("empty")
    else:
        if shared_counts.get(norm_desc(desc), 0) > 1:
            flags.append("shared")
        if is_run_on(desc):
            flags.append("run_on")
        if len(desc) < 300:
            flags.append("short")
        if PROMO_ORIG.search(desc):
            flags.append("promo")
    if has_markup(desc_raw):
        flags.append("markup")
    attrs = {k: first(r, k) for k in FACT_ATTRS if first(r, k)}
    used = {"id", id_key, "item_group_id", "title", "description", "product_highlight", "product_detail",
            "product_type", "google_product_category", "link"} | set(FACT_ATTRS)
    other = {}
    for k, vals in r.items():
        if k in used or k.startswith(DROP_PREFIXES):
            continue
        other[k] = vals if len(vals) > 1 else vals[0]
    g = ginfo.get(raw_id, {})
    return {
        "id": pid,
        "item_group_id": first(r, "item_group_id"),
        "title": first(r, "title"),
        "description_original": desc,
        "description_segments": html_segments(desc_raw),
        "original_flags": flags,
        "shared_with": max(0, shared_counts.get(norm_desc(desc), 0) - 1) if desc else 0,
        "brand": first(r, "brand"),
        "product_type": " | ".join(r.get("product_type", [])),
        "google_product_category": first(r, "google_product_category"),
        "highlights": r.get("product_highlight", []),
        "details": [parse_detail(v) for v in r.get("product_detail", [])],
        "attributes": attrs,
        "other": other,
        "link": first(r, "link"),
        "group": g.get("group", ""),
        "group_size": g.get("group_size", 1),
        "variant_attrs": g.get("variant_attrs", []),
        "variant_label": g.get("variant_label", ""),
        "variant_parts": g.get("variant_parts", []),
        "implicit_group": g.get("implicit_group", False),
    }


def match_pick(rows, id_key, item):
    item = item.strip()
    if not item:
        return []
    exact = [r for r in rows if first(r, id_key) == item]
    if exact:
        return exact
    low = item.lower()
    if low.startswith("http"):
        base = low.split("?")[0].rstrip("/")
        hits = [r for r in rows if first(r, "link").lower().split("?")[0].rstrip("/") == base]
        if hits:
            return hits
        handle = base.rsplit("/", 1)[-1]
        return [r for r in rows if handle and handle in first(r, "link").lower()]
    hits = [r for r in rows if first(r, "title").lower() == low]
    if hits:
        return hits
    return [r for r in rows if low in first(r, "title").lower()]


def run_paths(run):
    return {"dir": run, "config": os.path.join(run, "run-config.json"), "products": os.path.join(run, "products.jsonl"),
            "drafts": os.path.join(run, "drafts.jsonl"), "report": os.path.join(run, "check-report.json")}


def read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def write_jsonl(path, items):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "store").lower()).strip("-")
    return s or "store"


def cmd_normalise(a):
    p = run_paths(a.run)
    os.makedirs(a.run, exist_ok=True)
    if os.path.exists(p["products"]) and not a.force:
        sys.exit("products.jsonl already exists in %s. Use `next` to resume, or --force to rebuild the product list "
                 "(existing drafts are kept)." % a.run)
    headers, rows, meta = load_feed(a.feed)
    idp = pick_id_column(headers, rows, a.id_col)
    if idp["problem"]:
        sys.exit(idp["problem"])
    id_key = idp["column"]
    id_from_rest = bool(a.id_from_rest or idp["from_rest"])
    lang = detect_language(headers, rows, a.lang)
    ginfo = build_groups(rows, id_key)
    shared = {}
    for r in rows:
        d = flat_text(first(r, "description"))
        if d:
            shared[norm_desc(d)] = shared.get(norm_desc(d), 0) + 1

    picks = list(a.pick or [])
    if a.pick_file:
        with open(a.pick_file, encoding="utf-8") as f:
            picks += [ln.strip() for ln in f if ln.strip()]
    chosen, unmatched, ambiguous = [], [], []
    if a.all:
        chosen = rows
    elif a.first:
        chosen = rows[: a.first]
    elif picks:
        for it in picks:
            hits = match_pick(rows, id_key, it)
            if not hits:
                unmatched.append(it)
            groups_hit = {ginfo[first(h, id_key)]["group"] for h in hits}
            if len(groups_hit) > 1:
                ambiguous.append({"pick": it, "matched_products": len(hits)})
            chosen += hits
    else:
        sys.exit("Say which products to do: --pick / --pick-file / --first N / --all.")

    if not a.no_variants:
        wanted = {ginfo[first(r, id_key)]["group"] for r in chosen}
        chosen = [r for r in rows if ginfo[first(r, id_key)]["group"] in wanted]
    seen, ordered = set(), []
    # keep variants of a group next to each other, in feed order of first appearance
    order = []
    for r in rows:
        g = ginfo[first(r, id_key)]["group"]
        if g not in order:
            order.append(g)
    rank = {g: i for i, g in enumerate(order)}
    chosen = sorted(chosen, key=lambda r: rank[ginfo[first(r, id_key)]["group"]])
    for r in chosen:
        pid = first(r, id_key)
        if pid and pid not in seen:
            seen.add(pid)
            ordered.append(product_record(r, id_key, ginfo, shared, id_from_rest))
    missing_id = sum(1 for r in chosen if not first(r, id_key))
    write_jsonl(p["products"], ordered)
    cfg = {}
    if os.path.exists(p["config"]):
        with open(p["config"], encoding="utf-8") as f:
            cfg = json.load(f)
    cfg.update({"feed": os.path.abspath(a.feed), "id_column": id_key, "id_from_rest": id_from_rest,
                "language": lang["code"] or cfg.get("language", ""), "language_summary": lang["summary"],
                "store": a.store or cfg.get("store", ""),
                "products": len(ordered), "updated": datetime.datetime.now().isoformat(timespec="seconds")})
    with open(p["config"], "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print(json.dumps({"run": os.path.abspath(a.run), "products_selected": len(ordered),
                      "groups": len({x["group"] for x in ordered}),
                      "unmatched_picks": unmatched, "ambiguous_picks": ambiguous,
                      "rows_without_id_skipped": missing_id,
                      "id_column": id_key, "id_samples": idp["samples"], "ids_stripped_to_item_id": id_from_rest,
                      "id_notes": idp["notes"],
                      "language": lang["code"], "language_summary": lang["summary"],
                      "language_evidence": lang["evidence"], "language_confident": lang["confident"],
                      "variants_included": not a.no_variants}, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# next / add
# ---------------------------------------------------------------------------

def load_run(run):
    p = run_paths(run)
    if not os.path.exists(p["products"]):
        sys.exit("No products.jsonl in %s - run `normalise` first." % run)
    cfg = {}
    if os.path.exists(p["config"]):
        with open(p["config"], encoding="utf-8") as f:
            cfg = json.load(f)
    products = read_jsonl(p["products"])
    drafts = {d["id"]: d for d in read_jsonl(p["drafts"])}
    return p, cfg, products, drafts


def cmd_next(a):
    p, cfg, products, drafts = load_run(a.run)
    pending = [x for x in products if x["id"] not in drafts]
    batch = pending[: a.batch]
    if batch:
        last_group = batch[-1]["group"]
        for x in pending[a.batch: a.batch + 20]:
            if x["group"] == last_group:
                batch.append(x)
            else:
                break
    print(json.dumps({"done": len(drafts), "total": len(products), "this_batch": len(batch),
                      "remaining_after_this_batch": len(pending) - len(batch), "language": cfg.get("language", ""),
                      "products": batch}, indent=2, ensure_ascii=False))


def validate_draft(d, ids):
    errs = []
    if not isinstance(d, dict):
        return ["draft is not an object"]
    if d.get("id") not in ids:
        errs.append("unknown id %r" % d.get("id"))
    if d.get("status") not in ("ready", "hold"):
        errs.append("status must be 'ready' or 'hold'")
    if d.get("status") == "ready" and not (d.get("description") or "").strip():
        errs.append("ready draft has no description")
    if d.get("status") == "hold" and not (d.get("notes") or d.get("conflicts")):
        errs.append("hold draft needs notes or conflicts explaining why")
    for c in d.get("conflicts", []) or []:
        if not isinstance(c, dict) or "fact" not in c or not isinstance(c.get("sources"), list):
            errs.append("each conflict needs {fact, sources:[{source, says}]}")
    for lo in d.get("left_out", []) or []:
        if not isinstance(lo, dict) or "text" not in lo or "reason" not in lo:
            errs.append("each left_out item needs {text, reason}")
    pg = d.get("page")
    if pg is not None and (not isinstance(pg, dict) or pg.get("status") not in ("read", "failed", "skipped")):
        errs.append("page must be {url, status: read|failed|skipped, facts: [...]}")
    return errs


def cmd_add(a):
    p, cfg, products, drafts = load_run(a.run)
    ids = {x["id"] for x in products}
    with open(a.batch_file, encoding="utf-8") as f:
        txt = f.read().strip()
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        data = [json.loads(ln) for ln in txt.splitlines() if ln.strip()]
    if isinstance(data, dict):
        data = [data]
    problems = {}
    for d in data:
        errs = validate_draft(d, ids)
        if errs:
            problems[str(d.get("id"))] = errs
    if problems:
        print(json.dumps({"saved": 0, "problems": problems}, indent=2, ensure_ascii=False))
        sys.exit(1)
    for d in data:
        d["description"] = re.sub(r"\s+", " ", (d.get("description") or "")).strip()
        d["saved"] = datetime.datetime.now().isoformat(timespec="seconds")
        drafts[d["id"]] = d
    order = {x["id"]: i for i, x in enumerate(products)}
    write_jsonl(p["drafts"], sorted(drafts.values(), key=lambda d: order.get(d["id"], 10 ** 9)))
    print(json.dumps({"saved": len(data), "done": len(drafts), "total": len(products),
                      "remaining": len(products) - len(drafts)}, indent=2))


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

NUM = re.compile(r"\d+(?:[.,]\d+)*")
LINK = re.compile(r"(?i)(https?://|www\.|\b[a-z0-9-]+\.(com|co\.uk|com\.au|net|org|io|shop|store|de|fr|nl|ca)\b)")
PRICE = re.compile(r"([$£€¥₹]\s?\d|\b\d+(?:[.,]\d+)?\s?(USD|GBP|EUR|AUD|CAD|NZD|INR)\b)")
PROMO = re.compile(r"(?i)\b(free (shipping|delivery|returns?)|shipping|delivery|delivered|dispatch(ed)?|in stock|out of stock|"
                   r"on sale|sale price|discount(ed)?|coupon|promo(tion|tional)?|\d+\s?% off|buy now|order (now|today)|"
                   r"shop now|add to (cart|basket)|limited[- ]time|while stocks? last|returns? policy|money[- ]back|"
                   r"click here)\b")
SOFT_PROMO = re.compile(r"(?i)\b(limited[- ]edition|best[- ]?sell(er|ers|ing)|new arrival|brand[- ]new|"
                        r"just (launched|dropped|landed)|new for \d{4}|this season)\b")
SUPERLATIVES = ["best", "finest", "perfect", "ultimate", "unbeatable", "unmatched", "unrivalled", "unrivaled",
                "world-class", "revolutionary", "premium", "luxury", "luxurious", "greatest", "highest", "amazing",
                "incredible", "stunning", "must-have", "game-changer", "game-changing", "ideal", "superior",
                "exceptional", "outstanding", "top-quality", "number one", "#1"]
HEALTH = ["cure", "cures", "treat", "treats", "treatment", "heal", "heals", "healing", "relieve", "relieves", "relief",
          "pain", "aches", "therapeutic", "therapy", "medical", "clinically", "clinical", "orthopaedic", "orthopedic",
          "antibacterial", "anti-bacterial", "antimicrobial", "hypoallergenic", "allergy", "allergies",
          "eczema", "arthritis", "injury", "immune", "immunity", "detox", "anxiety", "insomnia", "disease",
          "prevent", "prevents", "prevention", "boost", "boosts", "boosting", "inflammation", "anti-inflammatory",
          "symptom", "symptoms", "cholesterol", "longevity", "anti-aging", "anti-ageing", "wellbeing", "well-being",
          "health", "healthy"]
COMPARE = re.compile(r"(?i)\b(better than|compared (to|with)|unlike (other|most|many)|versus|vs\.?|than (other|most|any))\b")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⬆↔-↪]")
BULLETS = re.compile("[•·▪●✓✔★☆]")
STOP = set("about above after again against along also among another around because been before being below between both "
           "built could does doing down during each every from further have having here into itself just made make more most "
           "much other over same should some such than that their them then there these they this those through under until "
           "very what when where which while with within without would your yours you're it's".split())

# US spelling -> GB spelling (unambiguous pairs only)
SPELL = [("color", "colour"), ("colors", "colours"), ("colored", "coloured"), ("colorful", "colourful"),
         ("gray", "grey"), ("aluminum", "aluminium"), ("center", "centre"), ("centers", "centres"),
         ("liter", "litre"), ("liters", "litres"), ("favorite", "favourite"), ("jewelry", "jewellery"),
         ("fiber", "fibre"), ("fibers", "fibres"), ("odor", "odour"), ("flavor", "flavour"), ("flavors", "flavours"),
         ("cozy", "cosy"), ("pajamas", "pyjamas"), ("traveler", "traveller"), ("travelers", "travellers"),
         ("traveling", "travelling"), ("labeled", "labelled"), ("catalog", "catalogue"), ("mold", "mould"),
         ("defense", "defence"), ("gage", "gauge"), ("plow", "plough"), ("aging", "ageing")]
GB_LIKE = {"en-gb", "en-au", "en-nz", "en-ie", "en-za", "en-in", "en-sg", "en-uk"}


def source_blob(prod, draft, claims_only=False):
    """All of a product's own text. claims_only leaves out the category paths, which name a category
    ("Health & Beauty") rather than make a claim, so they can't vouch for health wording."""
    parts = [prod.get("title", ""), prod.get("description_original", ""), prod.get("brand", ""),
             prod.get("variant_label", "")]
    if not claims_only:
        parts += [prod.get("product_type", ""), prod.get("google_product_category", "")]
    parts += prod.get("highlights", [])
    parts += ["%s %s %s" % (d.get("section", ""), d.get("name", ""), d.get("value", "")) for d in prod.get("details", [])]
    parts += list(prod.get("attributes", {}).values())
    for v in prod.get("other", {}).values():
        parts += v if isinstance(v, list) else [v]
    pg = draft.get("page") or {}
    parts += pg.get("facts", []) or []
    return " \n ".join(str(x) for x in parts if x)


def norm_num(n):
    n = n.replace(",", ".")
    if re.match(r"^\d+\.\d*0+$", n):
        n = n.rstrip("0").rstrip(".")
    return n


def stem(w):
    w = w.lower()
    return w[:-1] if w.endswith("s") and not w.endswith("ss") else w


def words(s):
    return re.findall(r"[a-zA-Zà-ÿÀ-ß][\w'-]*", s or "")


SIZE_WORDS = {"xxs": ["extra extra small", "2xs"], "xs": ["extra small", "extra-small"], "s": ["small"], "m": ["medium"],
              "l": ["large"], "xl": ["extra large", "extra-large"], "xxl": ["2xl", "extra extra large"],
              "xxxl": ["3xl"], "os": ["one size"], "o/s": ["one size"]}


def variant_pos(part, text):
    """Where a variant value first appears in the text (-1 if absent). Short values (S, M, XL) must stand alone."""
    best = -1
    for f in [part] + SIZE_WORDS.get(part.lower(), []):
        if len(f) <= 3:
            m = re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(f), text)
        else:
            m = re.search(r"(?<!\w)%s(?!\w)" % re.escape(f), text, re.I)
        if m and (best < 0 or m.start() < best):
            best = m.start()
    return best


def lint(prod, draft, all_drafts, lang):
    E, W = [], []
    text = draft.get("description") or ""
    if draft.get("status") == "hold":
        return E, ["held - not written; see notes"]
    src = source_blob(prod, draft)
    src_low = src.lower()
    thin = bool(draft.get("thin_data"))
    n = len(text)
    if n > 5000:
        E.append("over Google's 5,000-character limit (%d)" % n)
    if n < 100:
        E.append("too short to be useful (%d characters)" % n)
    elif not thin and (n < 500 or n > 900):
        W.append("length %d is outside the 500-900 band (aim for about 600-750)" % n)
    sc = sentence_count(text)
    if not thin and sc < 3:
        W.append("only %d full sentence(s); aim for 4-5" % sc)
    if sc > 6:
        W.append("%d sentences; aim for 4-5" % sc)
    if "\t" in text or "\n" in text or "\r" in text:
        E.append("contains a tab or line break")
    if text.startswith('"'):
        E.append("starts with a double quote (breaks some feed parsers) - rephrase")
    elif '"' in text:
        W.append('contains a double quote mark - some feed tools mangle it; write 12-inch rather than 12", and drop decorative quotes')
    if re.search(r"<[a-zA-Z/][^>]*>", text):
        E.append("contains HTML")
    if BULLETS.search(text):
        E.append("contains bullet or tick symbols - write full sentences")
    if "!" in text:
        E.append("exclamation mark (Google treats it as promotional)")
    if EMOJI.search(text):
        E.append("emoji or decorative symbol")
    if LINK.search(text):
        E.append("contains a link or web address: %s" % LINK.search(text).group(0))
    if PRICE.search(text):
        E.append("contains a price or currency: %s" % PRICE.search(text).group(0))
    m = PROMO.search(text)
    if m:
        E.append("promotional, shipping or policy wording: '%s'" % m.group(0))
    m = SOFT_PROMO.search(text)
    if m:
        W.append("'%s' is promotional, time-related or a policy - Google wants these out of the description" % m.group(0))
    if COMPARE.search(text):
        W.append("comparison wording ('%s') - Google does not allow comparisons to other products" % COMPARE.search(text).group(0))
    # numbers must come from the product's own data
    src_nums = {norm_num(x) for x in NUM.findall(src)}
    bad_nums = sorted({x for x in NUM.findall(text) if norm_num(x) not in src_nums})
    if bad_nums:
        E.append("number(s) not found in this product's data: %s" % ", ".join(bad_nums))
    low = text.lower()
    sup = [w for w in SUPERLATIVES if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), low)
           and not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), src_low)]
    if sup:
        W.append("superlative/hype word(s) not in the product data: %s" % ", ".join(sup))
    claim_low = source_blob(prod, draft, claims_only=True).lower()
    hl = [w for w in HEALTH if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), low)
          and not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), claim_low)]
    if hl:
        W.append("health/medical wording not in this product's data or page: %s - keep a health claim only as the "
                 "product's own data or page states it" % ", ".join(hl))
    caps = [w for w in words(text) if len(w) >= 4 and w.isupper() and w not in src]
    if caps:
        W.append("capitals not used in the product data (Google: no capitals for emphasis): %s" % ", ".join(sorted(set(caps))))
    # variant naming
    parts = [x for x in prod.get("variant_parts", []) if x]
    if prod.get("group_size", 1) > 1 and parts:
        found = {x: variant_pos(x, text) for x in parts}
        missing = [x for x, i in found.items() if i < 0]
        if missing:
            E.append("variant not named: %s (each variant's description must name it)" % ", ".join(missing))
        elif max(found.values()) > 220:
            W.append("name the variant (%s) in the opening sentence" % ", ".join(parts))
    # product name early
    tw = [w.lower() for w in words(prod.get("title", "")) if len(w) >= 4]
    opening = low[:220]
    if tw and sum(1 for w in set(tw[:6]) if w in opening) < min(2, len(set(tw[:6]))):
        W.append("the opening sentence should name the exact product (title words missing from the first 220 characters)")
    # uniqueness
    key = norm_desc(text)
    dupes = [d["id"] for d in all_drafts if d["id"] != draft["id"] and d.get("status") == "ready" and norm_desc(d.get("description")) == key]
    if dupes:
        E.append("identical to the description for: %s" % ", ".join(dupes[:5]))
    # market spelling (English only)
    lang_l = (lang or "").lower()
    title_attr = (prod.get("title", "") + " " + " ".join(prod.get("attributes", {}).values()) + " " + prod.get("brand", "")).lower()
    pairs = []
    if lang_l in GB_LIKE:
        pairs = [(us, gb) for us, gb in SPELL]
    elif lang_l == "en-us":
        pairs = [(gb, us) for us, gb in SPELL]
    elif lang_l == "en-ca":
        pairs = [(us, gb) for us, gb in SPELL if us in ("color", "colors", "colored", "colorful", "center", "centers", "favorite", "flavor", "flavors", "liter", "liters")]
    wrong = [w for w, right in pairs if re.search(r"\b%s\b" % w, low) and not re.search(r"\b%s\b" % w, title_attr)]
    if wrong:
        W.append("spelling for %s: %s" % (lang, ", ".join(wrong)))
    # conflicts must not leak into the copy
    for c in draft.get("conflicts", []) or []:
        for s in c.get("sources", []) or []:
            says = (s.get("says") or "").strip().lower()
            if len(says) >= 4 and says in low:
                W.append("conflicting fact '%s' (%s) appears in the copy - leave it out until a human decides" % (s.get("says"), c.get("fact")))
    # facts kept from the original
    orig = prod.get("description_original", "")
    left = " ".join(x.get("text", "") for x in draft.get("left_out", []) or []).lower()
    ow = {stem(w): w.lower() for w in words(orig) if len(w) >= 5 and w.lower() not in STOP and w.lower() not in left}
    if len(ow) >= 8:
        dw = {stem(w) for w in words(text)}
        miss = sorted(v for k, v in ow.items() if k not in dw)
        if len(miss) / len(ow) > 0.5:
            W.append("over half the words of the original are gone - check no fact was dropped (missing e.g.: %s)" % ", ".join(miss[:12]))
    return E, W


def run_check(run):
    p, cfg, products, drafts = load_run(run)
    lang = cfg.get("language", "")
    pmap = {x["id"]: x for x in products}
    dl = list(drafts.values())
    report = {}
    for d in dl:
        if d["id"] not in pmap:
            report[d["id"]] = {"errors": ["draft for an id that is not in products.jsonl"], "warnings": []}
            continue
        e, w = lint(pmap[d["id"]], d, dl, lang)
        report[d["id"]] = {"errors": e, "warnings": w}
    with open(p["report"], "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return p, cfg, products, drafts, report


def cmd_check(a):
    p, cfg, products, drafts, report = run_check(a.run)
    errs = {k: v["errors"] for k, v in report.items() if v["errors"]}
    warns = {k: v["warnings"] for k, v in report.items() if v["warnings"]}
    summary = {"drafts": len(drafts), "products": len(products), "not_written_yet": len(products) - len(drafts),
               "with_errors": len(errs), "with_warnings": len(warns), "errors": errs, "warnings": warns,
               "report_file": p["report"]}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if errs:
        sys.exit(1)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def esc(s):
    return html.escape(str(s or ""), quote=True)


def structured(text):
    return 'trained_algorithmic_media:"%s"' % text.replace('"', '""')


def bar_rows(items, total, cls=""):
    out = []
    for label, n in items:
        pct = 0 if not total else max(2, round(100 * n / total))
        out.append('<div class="hbar-row"><span class="hbar-label">%s</span><span class="hbar-track"><span class="hbar-fill %s" style="width:%d%%"></span></span><span class="hbar-val">%d of %d</span></div>'
                   % (esc(label), cls, pct, n, total))
    return "\n".join(out)


def cmd_build(a):
    p, cfg, products, drafts, report = run_check(a.run)
    errs = {k: v["errors"] for k, v in report.items() if v["errors"]}
    if errs and not a.force:
        print(json.dumps({"built": False, "reason": "fix the errors first (or --force)", "errors": errs}, indent=2, ensure_ascii=False))
        sys.exit(1)
    store = cfg.get("store") or "Your store"
    slug = slugify(store)
    lang = cfg.get("language") or ""
    pmap = {x["id"]: x for x in products}
    ready = [d for d in drafts.values() if d.get("status") == "ready" and d["id"] in pmap and not report.get(d["id"], {}).get("errors")]
    order = {x["id"]: i for i, x in enumerate(products)}
    ready.sort(key=lambda d: order[d["id"]])
    held = [d for d in drafts.values() if d.get("status") == "hold"]
    skipped_err = [k for k in errs]

    # 1. Supplemental feed (tab-separated, UTF-8, no BOM)
    tsv = os.path.join(a.run, "%s-supplemental-descriptions.tsv" % slug)
    with open(tsv, "w", encoding="utf-8", newline="") as f:
        f.write("id\tdescription\tstructured_description\n")
        for d in ready:
            text = re.sub(r"\s+", " ", d["description"]).strip()
            f.write("%s\t%s\t%s\n" % (d["id"], text, structured(text)))
    # verify what we wrote
    with open(tsv, encoding="utf-8") as f:
        lines = f.read().split("\n")
    body = [ln for ln in lines[1:] if ln]
    assert all(ln.count("\t") == 2 for ln in body), "TSV row with the wrong number of columns"
    tsv_ids = [ln.split("\t")[0] for ln in body]
    assert len(tsv_ids) == len(set(tsv_ids)), "duplicate id in TSV"
    assert set(tsv_ids) <= set(pmap), "TSV id not in the input products"

    # 2. Review page
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    total = len(products)
    orig_lens = [len(pmap[d["id"]]["description_original"]) for d in ready if pmap[d["id"]]["description_original"]]
    new_lens = [len(d["description"]) for d in ready]
    avg_b = round(sum(orig_lens) / len(orig_lens)) if orig_lens else 0
    avg_a = round(sum(new_lens) / len(new_lens)) if new_lens else 0
    variants_named = sum(1 for d in ready if pmap[d["id"]].get("group_size", 1) > 1 and pmap[d["id"]].get("variant_parts"))
    # conflicts, de-duplicated across the variants of a group
    conf = {}
    for d in drafts.values():
        prod = pmap.get(d["id"])
        if not prod:
            continue
        for c in d.get("conflicts", []) or []:
            k = (prod["group"], (c.get("fact") or "").strip().lower())
            entry = conf.setdefault(k, {"title": prod["title"], "fact": c.get("fact", ""), "sources": c.get("sources", []), "ids": []})
            entry["ids"].append(d["id"])
    content = []
    # stat row
    content.append('<div class="stat-row">')
    content.append('<div class="stat-card"><div class="num">%d</div><div class="lbl">new descriptions ready to upload%s</div></div>'
                   % (len(ready), (" (of %d products)" % total) if len(ready) != total else ""))
    content.append('<div class="stat-card"><div class="num">%d</div><div class="lbl">variants now named in their own description</div></div>' % variants_named)
    content.append('<div class="stat-card"><div class="num">%s&rarr;%s</div><div class="lbl">average characters, before &rarr; after</div></div>' % (avg_b, avg_a))
    content.append('<div class="stat-card%s"><div class="num">%d</div><div class="lbl">facts that need your decision</div></div>'
                   % (" hot" if conf else "", len(conf)))
    content.append('</div>')

    # visual 1 - what was wrong with the originals
    flag_names = [("shared", "Same text shared with another product"), ("run_on", "Run-on text: 200+ characters without a full stop"),
                  ("short", "Under 300 characters"), ("markup", "Contained HTML or markup"),
                  ("promo", "Promotional, shipping or time-related text"), ("empty", "No description at all")]
    items = [(lbl, sum(1 for x in products if k in x.get("original_flags", []))) for k, lbl in flag_names]
    items = [(l, n) for l, n in items if n]
    if items:
        content.append('<div class="viz-card"><div class="viz-title">What was wrong with the original descriptions</div>%s'
                       '<div class="viz-note">Counted across the %d products in this run. Google shows the description as plain text, so stripped HTML lists turn into one run-on block.</div></div>'
                       % (bar_rows(items, total), total))
    # visual 2 - length before and after
    rows = [(pmap[d["id"]], d) for d in ready][:40]
    if rows:
        mx = max([1000] + [len(x["description_original"]) for x, _ in rows] + [len(d["description"]) for _, d in rows])
        mx = int((mx + 249) // 250 * 250)
        def pos(v):
            return round(100.0 * v / mx, 2)
        dl = []
        for prod, d in rows:
            b, af = len(prod["description_original"]), len(d["description"])
            lo, hi = sorted((b, af))
            vl = prod.get("variant_label") if prod.get("group_size", 1) > 1 else ""
            room = 46 - (len(vl) + 3 if vl else 0)
            base = prod["title"]
            if vl:  # drop the variant values from the end of the title; they are shown after the dot
                changed = True
                while changed:
                    changed = False
                    for part in sorted(prod.get("variant_parts", []), key=len, reverse=True):
                        trimmed = base.rstrip(" -|/,:–—")
                        if part and trimmed.endswith(part) and len(trimmed) > len(part):
                            base, changed = trimmed[: -len(part)], True
                base = base.rstrip(" -|/,:–—")
            base = base if len(base) <= max(room, 16) else base[: max(room, 16) - 1].rstrip() + "…"
            label = (base + " · " + vl) if vl else base
            dl.append('<div class="db-row"><span class="db-label" title="%s">%s</span><span class="db-track">'
                      '<span class="db-line" style="left:%s%%;width:%s%%"></span>'
                      '<span class="db-dot before" style="left:%s%%" title="before: %d"></span>'
                      '<span class="db-dot after" style="left:%s%%" title="after: %d"></span></span>'
                      '<span class="db-val">%d &rarr; %d</span></div>'
                      % (esc(prod["id"]), esc(label), pos(lo), pos(hi) - pos(lo), pos(b), b, pos(af), af, b, af))
        more = len(ready) - len(rows)
        content.append('<div class="viz-card"><div class="viz-title">Length, before and after (characters)</div>'
                       '<div class="db-legend"><span><i class="db-dot-key before"></i>Before</span><span><i class="db-dot-key after"></i>After</span>'
                       '<span class="guide-key"><i class="db-band-key"></i>Target 600&ndash;750</span><span class="guide-key"><i class="db-mark-key"></i>Shoppers see about the first 500 before clicking</span></div>'
                       '<div class="db-wrap"><div class="db-guides"><span class="db-band" style="left:%s%%;width:%s%%"></span><span class="db-mark" style="left:%s%%"></span></div>%s</div>'
                       '<div class="viz-note">Scale 0&ndash;%d characters.%s</div></div>'
                       % (pos(600), pos(750) - pos(600), pos(500), "\n".join(dl), mx,
                          (" Showing the first 40 of %d." % len(ready)) if more > 0 else ""))
    # visual 3 - flags for review
    health = sum(1 for v in report.values() if any("health/medical" in w for w in v["warnings"]))
    left_counts = {}
    for d in drafts.values():
        for lo in d.get("left_out", []) or []:
            r = (lo.get("reason") or "other").strip().lower()
            r = "promotional or time-related" if re.search(r"promo|time|limited|season|new", r) else \
                "shipping, price or policy" if re.search(r"ship|deliver|price|policy|return", r) else \
                "conflicting fact" if "conflict" in r else \
                "not a product fact" if re.search(r"taxonom|internal|code|metadata|not a (product )?fact|navigation|tag", r) else \
                "health or medical claim" if re.search(r"health|medical", r) else "other"
            left_counts[r] = left_counts.get(r, 0) + 1
    flag_items = [("Facts needing your decision", len(conf)), ("Products held back (not in the feed file)", len(held) + len(skipped_err)),
                  ("Health wording not in the product's data", health)]
    flag_items += [("Left out: " + k, v) for k, v in sorted(left_counts.items(), key=lambda x: -x[1])]
    flag_items = [(l, n) for l, n in flag_items if n]
    if flag_items:
        mxf = max(n for _, n in flag_items)
        fr = []
        for l, n in flag_items:
            fr.append('<div class="hbar-row"><span class="hbar-label">%s</span><span class="hbar-track"><span class="hbar-fill accent" style="width:%d%%"></span></span><span class="hbar-val">%d</span></div>'
                      % (esc(l), max(4, round(100 * n / mxf)), n))
        content.append('<div class="viz-card"><div class="viz-title">Flags for your review</div>%s<div class="viz-note">Left-out items are text from the original or the product page that does not belong in a Shopping description, or facts the sources disagree on.</div></div>' % "\n".join(fr))

    # Section 01 - decisions
    sec = 1
    content.append('<div class="section"><div class="section-head"><span class="eyebrow">Section %02d</span><h2>Decisions for you</h2>'
                   '<p>Where the product\'s own sources disagree, the new description leaves the fact out. Decide which is right, fix it at the source, and the fact can go back in.</p></div>' % sec)
    if conf:
        trs = []
        for c in conf.values():
            says = "".join('<div class="says"><strong>%s:</strong> %s</div>' % (esc(s.get("source")), esc(s.get("says"))) for s in c["sources"])
            ids = c["ids"]
            idtxt = esc(", ".join(ids[:4])) + (" +%d more" % (len(ids) - 4) if len(ids) > 4 else "")
            trs.append("<tr><td>%s<div class=\"ids\">%s</div></td><td>%s</td><td>%s</td><td class=\"verdict-risk\">Left out until you decide</td></tr>"
                       % (esc(c["title"]), idtxt, esc(c["fact"]), says))
        content.append('<div class="tbl-wrap"><table><thead><tr><th>Product</th><th>Fact</th><th>What each source says</th><th>In the new copy</th></tr></thead><tbody>%s</tbody></table></div>' % "\n".join(trs))
    else:
        content.append('<div class="note-card">No conflicting facts found between the sources that were read.</div>')
    if held or skipped_err:
        lis = ["<li><strong>%s</strong> %s &mdash; %s</li>" % (esc(pmap.get(d["id"], {}).get("title", "")), esc(d["id"]), esc(d.get("notes") or "see conflicts")) for d in held]
        lis += ["<li><strong>%s</strong> %s &mdash; still has check errors: %s</li>" % (esc(pmap.get(k, {}).get("title", "")), esc(k), esc("; ".join(errs[k]))) for k in skipped_err]
        content.append('<div class="avoid"><h3>Held back &mdash; not in the supplemental feed</h3><ul>%s</ul></div>' % "".join(lis))
    content.append('</div>')

    # Section 02 - before and after
    sec += 1
    content.append('<div class="section"><div class="section-head"><span class="eyebrow">Section %02d</span><h2>Before and after</h2>'
                   '<p>Every product in the feed file, in feed order. &ldquo;Before&rdquo; is the description as Google receives it (HTML stripped).</p></div>' % sec)
    for d in ready:
        prod = pmap[d["id"]]
        chips = "".join('<span class="chip">%s</span>' % esc(v) for v in prod.get("variant_parts", []))
        b = prod["description_original"]
        warn = report.get(d["id"], {}).get("warnings", [])
        meta = []
        pg = d.get("page") or {}
        if pg.get("status"):
            meta.append("Product page: %s" % {"read": "read", "failed": "could not be read", "skipped": "not read"}[pg["status"]])
        for lo in d.get("left_out", []) or []:
            meta.append("Left out: &ldquo;%s&rdquo; (%s)" % (esc(lo.get("text")), esc(lo.get("reason"))))
        for c in d.get("conflicts", []) or []:
            meta.append("Conflict left out: %s" % esc(c.get("fact")))
        if d.get("thin_data"):
            meta.append("Thin data: kept short rather than padded")
        for w in warn:
            meta.append("Check: %s" % esc(w))
        content.append(
            '<div class="ba-card"><div class="ba-head"><div><h3>%s</h3><span class="ba-id">%s</span></div><div class="chips">%s</div></div>'
            '<div class="ba-grid"><div class="ba-col before"><span class="ba-lbl">Before &middot; %d characters</span><p>%s</p></div>'
            '<div class="ba-col after"><span class="ba-lbl">After &middot; %d characters &middot; %d sentences</span><p>%s</p></div></div>%s</div>'
            % (esc(prod["title"]), esc(d["id"]), chips, len(b), esc(b) if b else "<em>No description</em>",
               len(d["description"]), sentence_count(d["description"]), esc(d["description"]),
               ('<ul class="ba-meta">%s</ul>' % "".join("<li>%s</li>" % m for m in meta)) if meta else ""))
    content.append('</div>')

    out_html = tpl
    rep = {"{{STORE}}": esc(store), "{{DATE}}": datetime.date.today().isoformat(), "{{LANG}}": esc(lang or "not set"),
           "{{COUNT}}": str(len(ready)), "{{TSV_NAME}}": esc(os.path.basename(tsv)), "{{SEC_NEXT}}": "%02d" % (sec + 1),
           "<!--{{CONTENT}}-->": "\n".join(content)}
    for k, v in rep.items():
        out_html = out_html.replace(k, v)
    htmlp = os.path.join(a.run, "%s-description-review.html" % slug)
    with open(htmlp, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(json.dumps({"built": True, "supplemental_feed": os.path.abspath(tsv), "rows": len(ready),
                      "review_page": os.path.abspath(htmlp), "held_back": [d["id"] for d in held] + skipped_err,
                      "conflicts_for_decision": len(conf), "not_written_yet": len(products) - len(drafts)}, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inspect")
    s.add_argument("feed")
    s.set_defaults(fn=cmd_inspect)
    s = sub.add_parser("normalise", aliases=["normalize"])
    s.add_argument("feed")
    s.add_argument("--run", required=True)
    s.add_argument("--id-col", default="", help="override: only when the user names the item ID column")
    s.add_argument("--pick", action="append", help="an ID, product URL or title (repeatable)")
    s.add_argument("--pick-file", help="text file, one ID / URL / title per line")
    s.add_argument("--first", type=int)
    s.add_argument("--all", action="store_true")
    s.add_argument("--no-variants", action="store_true", help="do not pull in the other variants of a picked product")
    s.add_argument("--id-from-rest", action="store_true", help="force stripping online:en:US: prefixes (normally automatic)")
    s.add_argument("--lang", default="", help="override: only when the user states a language/spelling, e.g. en-GB")
    s.add_argument("--store", default="")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_normalise)
    s = sub.add_parser("next")
    s.add_argument("--run", required=True)
    s.add_argument("--batch", type=int, default=10)
    s.set_defaults(fn=cmd_next)
    s = sub.add_parser("add")
    s.add_argument("--run", required=True)
    s.add_argument("batch_file")
    s.set_defaults(fn=cmd_add)
    s = sub.add_parser("check")
    s.add_argument("--run", required=True)
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser("build")
    s.add_argument("--run", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
