#!/usr/bin/env python3
"""titletool.py - helper script for the product-title-optimizer skill (Big Flare Skills Pack).

Python 3.8+, standard library only. Nothing to install.

It does the mechanical work so the thinking can go into the titles:

  inspect   FEED                              Summarise a feed: columns, item ID column, variants, brands,
                                              categories, what is wrong with the current titles, language.
  normalise FEED --run DIR                    Turn the chosen products into one record shape
            (--top N | --pick ITEM ... | --pick-file F | --first N | --all)
            [--perf FILE] [--store NAME] [--brand-case own|reseller] [--end-brand NAME | --no-end-brand]
            [--no-variants] [--force] [--id-col COL] [--lang en-GB]
  terms     FILE --run DIR [--replace]        Load search term data (a Google Ads search terms report, or a
                                              saved query result). Merges with terms already loaded.
  planner   FILE --run DIR [--category NAME]  Load Keyword Planner ideas (an export, or a saved result).
  categories --run DIR                        Categories with their top products, best-matching search terms
                                              and planner keywords: the brief for the research step.
  research  --run DIR NOTES.json              Save category research notes (merged by category).
  next      --run DIR [--batch 20]            The next products without a title, each with its best-matching
                                              search terms and its category's keywords (resume-safe).
  add       --run DIR BATCH.json              Validate titles and save them to DIR/drafts.jsonl
                                              (a draft for an ID that already has one replaces it).
  check     --run DIR                         Lint every title against the rules (length, brand, variants...).
  build     --run DIR [--force]               Write the supplemental feed (.tsv), the review workbook (.xlsx)
                                              and the review page (.html).
  apply     EDITED_FILE --run DIR [--force]   Read the user's edits back from the review workbook, re-check,
                                              and rebuild the outputs.

Accepted feed files: Google Shopping XML (RSS 2.0 or Atom with g: tags), delimited text
(.tsv/.txt/.csv - tab, comma, semicolon or pipe), and .xlsx (first sheet).
Reports (search terms, Keyword Planner, product performance) may start with Google's title lines;
the script finds the header row itself.
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


SEP_TOKEN = re.compile(r"^[-|/,:–—]+$")


def common_title_suffix(titles):
    """Shared ending of every title that starts at a separator, e.g. " | Store Name - Slogan".

    Only cut from a separator so a shared unit stays with its value ("500 ml" / "750 ml" keep "ml")."""
    out = []
    for parts in zip(*[t.split()[::-1] for t in titles]):
        if all(p == parts[0] for p in parts):
            out.append(parts[0])
        else:
            break
    out.reverse()
    for i, w in enumerate(out):
        if SEP_TOKEN.match(w):
            return " " + " ".join(out[i:])
    return ""


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
        suffix = common_title_suffix([first(m, "title") for m in members]) if len(members) > 1 else ""
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
                if suffix and rest.endswith(suffix) and len(rest) > len(suffix):
                    rest = rest[:-len(suffix)]  # drop a shared " | Store - Slogan" ending
                rest = rest.strip(" -|/,:–—")
                label = rest
                parts = [p.strip() for p in re.split(r"\s*[/|,]\s*|\s+[-–—]\s+", rest) if p.strip()] if rest else []
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



def parse_detail(v):
    parts = v.split(":")
    if len(parts) >= 3:
        return {"section": parts[0].strip(), "name": parts[1].strip(), "value": ":".join(parts[2:]).strip()}
    if len(parts) == 2:
        return {"section": "", "name": parts[0].strip(), "value": parts[1].strip()}
    return {"section": "", "name": "", "value": v.strip()}



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


NUM = re.compile(r"\d+(?:[.,]\d+)*")
LINK = re.compile(r"(?i)(https?://|www\.|\b[a-z0-9-]+\.(com|co\.uk|com\.au|net|org|io|shop|store|de|fr|nl|ca)\b)")
PRICE = re.compile(r"([$£€¥₹]\s?\d[\d,.]*|\b\d+(?:[.,]\d+)?\s?(USD|GBP|EUR|AUD|CAD|NZD|INR)\b)")
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
          "eczema", "arthritis", "injury", "immune", "immunity", "detox", "anxiety", "insomnia", "disease"]
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


# ===========================================================================
# Title-specific code (everything above is shared with the description writer)
# ===========================================================================

for _n in range(1, 6):
    for _src in ("shopping_product_product_type_level%d", "product_type_level%d", "product_type_level_%d", "product_type_l%d"):
        ALIASES[_src % _n] = "product_type_l%d" % _n
    for _src in ("shopping_product_category_level%d", "category_level%d", "category_level_%d", "google_category_l%d"):
        ALIASES[_src % _n] = "google_category_l%d" % _n
ALIASES.update({
    "impr": "impressions", "metrics_impressions": "impressions",
    "conv": "conversions", "metrics_conversions": "conversions",
    "metrics_clicks": "clicks",
    "shopping_product_item_id": "item_id", "segments_product_item_id": "item_id", "product_item_id": "item_id",
    "shopping_product_title": "title", "shopping_product_brand": "brand",
    "search_terms": "search_term", "search_query": "search_term", "query": "search_term",
    "search_term_view_search_term": "search_term",
    "campaign_search_term_insight_category_label": "category_label",
    "average_monthly_searches": "avg_monthly_searches", "avg_searches": "avg_monthly_searches",
    "monthly_searches": "avg_monthly_searches", "search_volume": "avg_monthly_searches",
    "keyword_text": "keyword", "keyword_idea": "keyword", "keyword_idea_text": "keyword",
    "new_title_edit_here": "new_title", "optimized_title": "new_title", "optimised_title": "new_title",
})

PERF_KEYS = ("clicks", "impressions", "conversions")
SOURCES = ("search_terms", "keyword_planner", "website", "web_search", "product_data", "ai")
SOURCE_NAMES = {"search_terms": "Your search terms", "keyword_planner": "Keyword Planner", "website": "Your website",
                "web_search": "Other websites", "product_data": "Product data", "ai": "Claude's ideas"}
TARGET_MIN, TARGET_MAX, HARD_MAX, SEEN = 130, 150, 150, 70


def num(v):
    s = str(v or "").strip().replace(",", "").replace(" ", "").replace("%", "")
    m = re.match(r"^-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else 0.0


def volume(v):
    """Keyword Planner volume: '1,300' -> 1300; a range '1K – 10K' -> 1000 (its lower end)."""
    s = str(v or "").strip()
    if not s or s in ("--", "-"):
        return None, s

    def one(x):
        x = x.strip().upper().replace(",", "")
        mult = 1
        if x.endswith("K"):
            mult, x = 1000, x[:-1]
        elif x.endswith("M"):
            mult, x = 1000000, x[:-1]
        try:
            return float(x) * mult
        except ValueError:
            return None
    vals = [one(x) for x in re.split(r"\s*[–—]\s*|\s+-\s+", s) if x.strip()]
    vals = [x for x in vals if x is not None]
    return (int(vals[0]) if vals else None), s


def same_name(a, b):
    a = re.sub(r"[^a-z0-9]", "", (a or "").lower())
    b = re.sub(r"[^a-z0-9]", "", (b or "").lower())
    return bool(a and b and (a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a))))


def clean_title(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    return re.sub(r"\s*\|\s*", " | ", t)


def sections(t):
    return [s.strip() for s in (t or "").split("|")]


# ---------------------------------------------------------------------------
# Reading reports (Google Ads exports start with title lines; find the header)
# ---------------------------------------------------------------------------

def read_xlsx_table(path, sheet_name=None):
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
    sheets = wb.find(m + "sheets").findall(m + "sheet")
    sheet = next((s for s in sheets if sheet_name and s.get("name") == sheet_name), sheets[0])
    rid = sheet.get(r + "id")
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next((rel.get("Target") for rel in rels if rel.get("Id") == rid), None) or "worksheets/sheet1.xml"
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
    return table, sheet.get("name")


TOTAL_ROW = re.compile(r"(?i)^total(:|\s*[-–]|$)")


def table_rows(path, want, sheet_name=None):
    """Read a table whose header row contains one of `want` (normalised column names), skipping report title
    lines above it and 'Total:' rows below. Returns (headers, rows, meta)."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"PK":
        table, sheet = read_xlsx_table(path, sheet_name)
        meta = {"format": "xlsx", "sheet": sheet}
        hi = next((i for i, row in enumerate(table[:25]) if any(norm_key(c) in want for c in row)), 0)
        table = table[hi:]
        meta["header_row"] = hi + 1
    else:
        head = raw[:500].lstrip(b"\xef\xbb\xbf \t\r\n")
        if head.startswith(b"<"):
            return read_xml(raw)
        text = decode(raw)
        lines = text.splitlines()
        hi, delim = None, None
        for i, ln in enumerate(lines[:25]):
            for d in ["\t", ",", ";", "|"]:
                if d in ln and any(norm_key(c) in want for c in next(csv.reader([ln], delimiter=d))):
                    hi, delim = i, d
                    break
            if delim:
                break
        if delim is None:
            return read_delimited(text)
        table = list(csv.reader(io.StringIO("\n".join(lines[hi:])), delimiter=delim))
        meta = {"format": "delimited", "header_row": hi + 1}
    headers, rows = rows_from_table(table)
    first_col = headers[0] if headers else ""
    rows = [x for x in rows if not TOTAL_ROW.match(first(x, first_col))]
    return headers, rows, meta


def load_perf(path):
    """Clicks/impressions/conversions by item ID (case-insensitive: Google Ads reports often lower-case IDs)."""
    headers, rows, meta = table_rows(path, {"item_id", "id", "offer_id"})
    col = next((c for c in ("item_id", "id", "offer_id") if c in headers), None)
    if not col:
        sys.exit("No item ID column in %s. Columns: %s" % (path, ", ".join(headers)))
    if not any(k in headers for k in PERF_KEYS):
        sys.exit("No clicks, impressions or conversions column in %s. Columns: %s" % (path, ", ".join(headers)))
    out = {}
    for r in rows:
        pid = first(r, col)
        m = REST_ID.match(pid) or MERCHANT_API_ID.match(pid)
        if m:
            pid = m.groups()[-1]
        if not pid:
            continue
        e = out.setdefault(pid.lower(), {k: 0.0 for k in PERF_KEYS})
        for k in PERF_KEYS:
            e[k] += num(first(r, k))
    return out


def row_perf(r, id_key, perf):
    if any(k in r for k in PERF_KEYS):
        return {k: num(first(r, k)) for k in PERF_KEYS}
    if perf:
        pid = first(r, id_key)
        m = REST_ID.match(pid) or MERCHANT_API_ID.match(pid)
        if m:
            pid = m.groups()[-1]
        return dict(perf.get(pid.lower(), {k: 0.0 for k in PERF_KEYS}))
    return None


# ---------------------------------------------------------------------------
# Products, categories, brand case
# ---------------------------------------------------------------------------

def levels_path(r, prefix):
    return " > ".join(x for x in (first(r, "%s_l%d" % (prefix, n)) for n in range(1, 6)) if x)


PATH_SEPS = [(">", r"\s*>\s*"), (" / ", r"\s+/\s+"), (" - ", r"\s+-\s+")]


def split_path(s, sep=r"\s*>\s*"):
    return [x.strip() for x in re.split(sep, s or "") if x.strip()]


def path_separator(values):
    """Product types are usually 'A > B > C'; some stores use ' / ' or ' - '. Pick the one the data uses."""
    vals = [v for v in values if v]
    best, n_best = PATH_SEPS[0][1], 0
    for lit, rx in PATH_SEPS:
        n = sum(1 for v in vals if lit in v)
        if n > n_best and n >= len(vals) * 0.5:
            best, n_best = rx, n
        if lit == ">" and n:
            return rx
    return best


def product_record(r, id_key, ginfo, id_from_rest, perf):
    raw_id = first(r, id_key)
    pid = raw_id
    if id_from_rest:
        m = REST_ID.match(raw_id) or MERCHANT_API_ID.match(raw_id)
        if m:
            pid = m.groups()[-1]
    g = ginfo.get(raw_id, {})
    rec = {
        "id": pid,
        "item_group_id": first(r, "item_group_id"),
        "title": re.sub(r"\s+", " ", first(r, "title")).strip(),
        "brand": first(r, "brand"),
        "product_type": " | ".join(r.get("product_type", [])) or levels_path(r, "product_type"),
        "google_product_category": first(r, "google_product_category") or levels_path(r, "google_category"),
        "description": flat_text(first(r, "description")),
        "highlights": r.get("product_highlight", [])[:10],
        "details": [parse_detail(v) for v in r.get("product_detail", [])][:15],
        "attributes": {k: first(r, k) for k in FACT_ATTRS if first(r, k)},
        "link": first(r, "link"),
        "group": g.get("group", "i:" + pid),
        "group_size": g.get("group_size", 1),
        "variant_attrs": g.get("variant_attrs", []),
        "variant_label": g.get("variant_label", ""),
        "variant_parts": g.get("variant_parts", []),
    }
    p = row_perf(r, id_key, perf)
    if p is not None:
        rec.update({k: int(round(v)) if k != "conversions" else round(v, 2) for k, v in p.items()})
    return rec


def assign_categories(products, cap=15):
    """One research category per product: the deepest product-type level with at most `cap` distinct values."""
    pts = [p.get("product_type", "").split(" | ")[0] for p in products]
    sep = path_separator(pts)
    paths = []
    for p, pt in zip(products, pts):
        paths.append(split_path(pt, sep) or split_path(p.get("google_product_category", "")))
    depth = 1
    for d in (1, 2, 3):
        vals = {" > ".join(x[:d]) for x in paths if x}
        if len(vals) > cap:
            break
        depth = d
    for p, x in zip(products, paths):
        p["category"] = " > ".join(x[:depth]) if x else "All products"


LABEL_WORDS = re.compile(r"(?i)\b(sale|clearance|outlet|semi-?annual|seasonal|archive|default|vendor|warehouse|gift ?card)\b")


def looks_like_label(b):
    """A brand value that is an internal label (a season code, a sale tag), not the maker of the product."""
    return bool(b and (re.search(r"(?i)\b(?:[a-z]{1,3}\d{2}|\d{2,4})\b", b) or LABEL_WORDS.search(b)))


def compact(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def needs_product_brand(pb, case, end):
    """Does this product's own brand have to be in the first half of its title?"""
    if not pb or looks_like_label(pb) or (end and same_name(pb, end)):
        return False
    return case == "reseller" or bool(end)


def decide_brand(brands, store, case_override="", end_override=None):
    """Own brand or reseller, and which name (if any) ends every title."""
    named = [b.strip() for b in brands if b and b.strip()]
    labels = sorted({b for b in named if looks_like_label(b) and not (store and compact(b) == compact(store))})
    named = [b for b in named if b not in labels or (store and same_name(store, b))]
    counts = {}
    for b in named:
        counts[b] = counts.get(b, 0) + 1
    top = sorted(counts.items(), key=lambda x: -x[1])
    notes = []
    if case_override:
        case, why = case_override, "set by the user"
    elif not named:
        case, why = "own", "the feed has no brand values"
    elif len(top) == 1:
        case, why = "own", "one brand across the products (%s)" % top[0][0]
        if store and not same_name(store, top[0][0]):
            notes.append("The feed's brand '%s' differs from the store name '%s'. If the store resells this brand "
                         "rather than making it, rerun with --brand-case reseller." % (top[0][0], store))
    else:
        own_share = sum(n for b, n in top if store and same_name(store, b)) / float(len(named))
        if own_share >= 0.8:
            case, why = "own", "%d%% of products carry the store's own brand" % round(own_share * 100)
        else:
            case, why = "reseller", "%d different brands across the products" % len(top)
    if end_override is not None:
        end = end_override
    elif case == "own":
        exact = [b for b, _ in top if store and compact(b) == compact(store)]
        if exact:
            end = exact[0]
        elif store and any(same_name(store, b) for b, _ in top):
            end = store
        else:
            end = top[0][0] if top else (store or "")
    else:
        end = ""
        notes.append("Reseller: each product's own brand goes in the first half of its title. The store's name is not "
                     "added, because Google's title rules say not to add your company's name. Use --end-brand NAME "
                     "only if the user asks for it.")
    if not end and case == "own":
        notes.append("No brand name to end the titles with: pass --store or --end-brand.")
    if labels:
        notes.append("These brand values look like internal labels (season codes, sale tags), not makers, so they are "
                     "ignored for the brand rule: %s" % ", ".join(labels[:8]))
    return {"case": case, "why": why, "end_brand": end, "brands_seen": [{"brand": b, "products": n} for b, n in top[:8]],
            "labels_ignored": labels[:8], "notes": notes}


TITLE_PROMO = re.compile(r"(?i)\b(free (shipping|delivery|returns?|gift)|(?<!for )sale|sale price|\d+\s?% off|discount(ed)?|"
                         r"new arrivals?|just (arrived|landed|dropped)|hot deals?|deal of the day|"
                         r"coupon|promo(tion|tional)?( code)?|buy now|order (now|today)|shop now|limited[- ]time|"
                         r"in stock|out of stock|clearance|while stocks? last|best price|lowest price|"
                         r"fast (shipping|delivery)|next[- ]day delivery|click here)\b")
SOFT_PROMO_T = re.compile(r"(?i)\b(best[- ]?sell(er|ers|ing)|limited[- ]edition|brand[- ]new|exclusive)\b")
TIME_TEXT = re.compile(r"(?i)\b(new for (19|20)\d\d|this (season|week|month)|black friday|cyber monday|"
                       r"(19|20)\d\d (sale|collection|edition))\b")


def caps_words(t):
    return [w for w in words(t) if len(w) >= 4 and w.isupper()]


def title_flags(p, title_counts, end_brand, case):
    t = p.get("title", "")
    n = len(t)
    f = []
    if not t:
        return ["empty"]
    if n < SEEN:
        f.append("under_70")
    if n < TARGET_MIN:
        f.append("short")
    if n > HARD_MAX:
        f.append("over_150")
    if title_counts.get(t.lower(), 0) > 1:
        f.append("duplicate")
    for b in [end_brand] if end_brand else []:
        if t.lower().startswith(b.lower()):
            f.append("brand_first")
    pb = p.get("brand", "")
    if needs_product_brand(pb, case, end_brand) and pb.lower() not in t.lower():
        f.append("brand_missing")
    if p.get("group_size", 1) > 1 and any(variant_pos(x, t) < 0 for x in p.get("variant_parts", []) if x):
        f.append("variant_missing")
    if TITLE_PROMO.search(t) or TIME_TEXT.search(t) or "!" in t:
        f.append("promo")
    if caps_words(t):
        f.append("caps")
    return f


FLAG_NAMES = [("under_70", "Under 70 characters: most of the 150 unused"),
              ("short", "Under 130 characters: room left for keywords"),
              ("duplicate", "Same title as another product"),
              ("variant_missing", "Size, colour or other variant not in the title"),
              ("brand_missing", "Product brand missing (a brand you resell)"),
              ("brand_first", "Starts with the store brand"),
              ("promo", "Promotional or time-related text"),
              ("caps", "Words in capitals"),
              ("over_150", "Over 150 characters: Google cuts the end off"),
              ("empty", "No title")]


def read_cfg(run):
    path = os.path.join(run, "run-config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_cfg(run, cfg):
    os.makedirs(run, exist_ok=True)
    with open(os.path.join(run, "run-config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def run_paths(run):
    j = lambda n: os.path.join(run, n)
    return {"dir": run, "config": j("run-config.json"), "products": j("products.jsonl"), "drafts": j("drafts.jsonl"),
            "terms": j("terms.jsonl"), "planner": j("planner.jsonl"), "research": j("research.json"),
            "report": j("check-report.json")}


def click_coverage(rows_perf):
    vals = sorted((c for c in rows_perf if c), reverse=True)
    total = sum(vals)
    if not total:
        return None
    out = {"products_with_clicks": len(vals), "total_clicks": int(total)}
    for n in (25, 50, 100, 250):
        out["top_%d_share_of_clicks" % n] = "%d%%" % round(100.0 * sum(vals[:n]) / total)
    return out


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
    idp = pick_id_column(headers, rows, a.id_col)
    out["item_id"] = {"column": idp["column"], "samples": idp["samples"], "strip_to_item_id": idp["from_rest"],
                      "notes": idp["notes"], "problem": idp["problem"]}
    id_key = idp["column"] or "id"
    perf = load_perf(a.perf) if a.perf else None
    perfs = [row_perf(r, id_key, perf) for r in rows]
    if any(x is not None for x in perfs):
        out["performance"] = click_coverage([x["clicks"] if x else 0 for x in perfs]) or \
            "performance columns found, but no clicks recorded"
    else:
        out["performance"] = "none: the feed has no clicks (pass --perf with a product performance report to rank products)"
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
    }
    brand = decide_brand([first(r, "brand") for r in rows], a.store)
    out["brand"] = brand
    recs = [product_record(r, id_key, ginfo, idp["from_rest"], perf) for r in rows]
    assign_categories(recs)
    cats = {}
    for x in recs:
        cats[x["category"]] = cats.get(x["category"], 0) + 1
    out["categories"] = [{"category": c, "products": n} for c, n in sorted(cats.items(), key=lambda x: -x[1])[:20]]
    if len(cats) > 20:
        out["categories_not_shown"] = len(cats) - 20
    tc = {}
    for x in recs:
        tc[x["title"].lower()] = tc.get(x["title"].lower(), 0) + 1
    flags = [title_flags(x, tc, brand["end_brand"], brand["case"]) for x in recs]
    lens = [len(x["title"]) for x in recs if x["title"]]
    out["titles"] = {"avg_length": round(sum(lens) / len(lens)) if lens else 0,
                     "min_length": min(lens) if lens else 0, "max_length": max(lens) if lens else 0}
    out["titles"].update({k: sum(1 for f in flags if k in f) for k, _ in FLAG_NAMES})
    out["has_links"] = sum(1 for r in rows if first(r, "link"))
    out["language"] = detect_language(headers, rows, a.lang)
    out["sample_titles"] = [x["title"] for x in recs[:6]]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_normalise(a):
    p = run_paths(a.run)
    os.makedirs(a.run, exist_ok=True)
    if os.path.exists(p["products"]) and not a.force:
        sys.exit("products.jsonl already exists in %s. Use `next` to resume, or --force to rebuild the product list "
                 "(existing titles are kept)." % a.run)
    headers, rows, meta = load_feed(a.feed)
    idp = pick_id_column(headers, rows, a.id_col)
    if idp["problem"]:
        sys.exit(idp["problem"])
    id_key = idp["column"]
    id_from_rest = bool(a.id_from_rest or idp["from_rest"])
    lang = detect_language(headers, rows, a.lang)
    perf = load_perf(a.perf) if a.perf else None
    ginfo = build_groups(rows, id_key)

    # one row per ID (a feed or report can list a product per country); keep the one with most clicks
    best = {}
    for r in rows:
        pid = first(r, id_key)
        if not pid:
            continue
        pf = row_perf(r, id_key, perf) or {}
        if pid not in best or pf.get("clicks", 0) > (row_perf(best[pid], id_key, perf) or {}).get("clicks", 0):
            best[pid] = r
    rows_u = [r for r in rows if first(r, id_key) and best.get(first(r, id_key)) is r]
    dupes_merged = len([r for r in rows if first(r, id_key)]) - len(rows_u)

    picks = list(a.pick or [])
    if a.pick_file:
        with open(a.pick_file, encoding="utf-8") as f:
            picks += [ln.strip() for ln in f if ln.strip()]
    chosen, unmatched, ambiguous = [], [], []
    if a.all:
        chosen = rows_u
    elif a.top:
        clicks = {first(r, id_key): (row_perf(r, id_key, perf) or {}).get("clicks", 0) for r in rows_u}
        if not any(clicks.values()):
            sys.exit("--top needs clicks: the feed has no clicks column and no --perf report was given. Ask the user "
                     "to name their top sellers, or to download a product performance report from Google Ads.")
        chosen = sorted(rows_u, key=lambda r: -clicks[first(r, id_key)])[: a.top]
    elif a.first:
        chosen = rows_u[: a.first]
    elif picks:
        for it in picks:
            hits = [h for h in match_pick(rows_u, id_key, it)]
            if not hits:
                unmatched.append(it)
            if len({ginfo[first(h, id_key)]["group"] for h in hits}) > 1:
                ambiguous.append({"pick": it, "matched_products": len(hits)})
            chosen += hits
    else:
        sys.exit("Say which products to do: --top N / --pick / --pick-file / --first N / --all.")
    if not a.no_variants:
        wanted = {ginfo[first(r, id_key)]["group"] for r in chosen}
        chosen = [r for r in rows_u if ginfo[first(r, id_key)]["group"] in wanted]
    order = []
    for r in rows_u:
        g = ginfo[first(r, id_key)]["group"]
        if g not in order:
            order.append(g)
    rank = {g: i for i, g in enumerate(order)}
    seen, recs = set(), []
    for r in sorted(chosen, key=lambda r: rank[ginfo[first(r, id_key)]["group"]]):
        pid = first(r, id_key)
        if pid not in seen:
            seen.add(pid)
            recs.append(product_record(r, id_key, ginfo, id_from_rest, perf))
    # categories come from the whole feed, so a run of 30 products gets the store's real categories
    whole = [product_record(r, id_key, ginfo, id_from_rest, None) for r in rows_u]
    assign_categories(whole)
    cat_of = {x["id"]: x["category"] for x in whole}
    for x in recs:
        x["category"] = cat_of.get(x["id"], "All products")
    end_override = "" if a.no_end_brand else (a.end_brand if a.end_brand else None)
    brand = decide_brand([first(r, "brand") for r in rows_u], a.store, a.brand_case, end_override)
    tc = {}
    for x in recs:
        tc[x["title"].lower()] = tc.get(x["title"].lower(), 0) + 1
    for x in recs:
        x["original_flags"] = title_flags(x, tc, brand["end_brand"], brand["case"])
    write_jsonl(p["products"], recs)
    cfg = read_cfg(a.run)
    cfg.update({"feed": os.path.abspath(a.feed), "id_column": id_key, "id_from_rest": id_from_rest,
                "language": lang["code"] or cfg.get("language", ""), "language_summary": lang["summary"],
                "store": a.store or cfg.get("store", ""), "brand_case": brand["case"], "brand_why": brand["why"],
                "end_brand": brand["end_brand"], "products": len(recs),
                "has_clicks": any("clicks" in x for x in recs),
                "updated": datetime.datetime.now().isoformat(timespec="seconds")})
    write_cfg(a.run, cfg)
    cov = None
    if cfg["has_clicks"]:
        allc = sum((row_perf(r, id_key, perf) or {}).get("clicks", 0) for r in rows_u)
        mine = sum(x.get("clicks", 0) for x in recs)
        cov = "%d%% of all product clicks" % round(100.0 * mine / allc) if allc else None
    cats = {}
    for x in recs:
        cats[x["category"]] = cats.get(x["category"], 0) + 1
    print(json.dumps({"run": os.path.abspath(a.run), "products_selected": len(recs),
                      "variant_groups": len({x["group"] for x in recs}), "selected_products_cover": cov,
                      "duplicate_rows_merged": dupes_merged,
                      "unmatched_picks": unmatched, "ambiguous_picks": ambiguous,
                      "id_column": id_key, "id_samples": idp["samples"], "ids_stripped_to_item_id": id_from_rest,
                      "id_notes": idp["notes"],
                      "language": lang["code"], "language_summary": lang["summary"],
                      "language_evidence": lang["evidence"], "language_confident": lang["confident"],
                      "brand": brand, "categories": cats,
                      "variants_included": not a.no_variants}, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Search terms, Keyword Planner, matching
# ---------------------------------------------------------------------------

def cmd_terms(a):
    p = run_paths(a.run)
    os.makedirs(a.run, exist_ok=True)
    headers, rows, meta = table_rows(a.file, {"search_term", "category_label"})
    col = next((c for c in ("search_term", "category_label") if c in headers), None)
    if not col:
        sys.exit("No search term column in %s (looked for 'Search term'). Columns: %s" % (a.file, ", ".join(headers)))
    label = a.label or ("pmax_category" if col == "category_label" else os.path.basename(a.file))
    agg = {} if a.replace else {t["term"].lower(): t for t in read_jsonl(p["terms"])}
    added = 0
    for r in rows:
        t = re.sub(r"\s+", " ", first(r, col)).strip()
        if not t or t in ("--", "Uncategorized", "uncategorized"):
            continue
        e = agg.get(t.lower())
        if not e:
            e = agg[t.lower()] = {"term": t, "impressions": 0, "clicks": 0, "conversions": 0.0, "from": []}
            added += 1
        for k in PERF_KEYS:
            e[k] = round(e[k] + num(first(r, k)), 2) if k == "conversions" else int(e[k] + num(first(r, k)))
        if label not in e["from"]:
            e["from"].append(label)
    items = sorted(agg.values(), key=lambda x: (-x["impressions"], -x["clicks"]))
    write_jsonl(p["terms"], items)
    missing = [k for k in PERF_KEYS if k not in headers]
    print(json.dumps({"file": os.path.abspath(a.file), "read_from_row": meta.get("header_row"), "column": col,
                      "new_terms": added, "terms_total": len(items),
                      "impressions_total": sum(x["impressions"] for x in items),
                      "clicks_total": sum(x["clicks"] for x in items),
                      "missing_columns": missing,
                      "top_terms": [{"term": x["term"], "impressions": x["impressions"], "clicks": x["clicks"]}
                                    for x in items[:12]]}, indent=2, ensure_ascii=False))


def cmd_planner(a):
    p = run_paths(a.run)
    os.makedirs(a.run, exist_ok=True)
    headers, rows, meta = table_rows(a.file, {"keyword"})
    if "keyword" not in headers:
        sys.exit("No 'Keyword' column in %s. Columns: %s" % (a.file, ", ".join(headers)))
    agg = {k["keyword"].lower(): k for k in read_jsonl(p["planner"])}
    added = 0
    for r in rows:
        kw = re.sub(r"\s+", " ", first(r, "keyword")).strip()
        if not kw:
            continue
        vol, vtext = volume(first(r, "avg_monthly_searches"))
        e = agg.get(kw.lower())
        if not e:
            e = agg[kw.lower()] = {"keyword": kw, "monthly_searches": vol, "volume_text": vtext,
                                   "competition": first(r, "competition"), "categories": []}
            added += 1
        elif vol is not None and (e.get("monthly_searches") or 0) < vol:
            e["monthly_searches"], e["volume_text"] = vol, vtext
        if a.category and a.category not in e["categories"]:
            e["categories"].append(a.category)
    items = sorted(agg.values(), key=lambda x: -(x.get("monthly_searches") or 0))
    write_jsonl(p["planner"], items)
    ranged = sum(1 for x in items if re.search(r"[–—]|\s-\s", x.get("volume_text") or ""))
    print(json.dumps({"file": os.path.abspath(a.file), "read_from_row": meta.get("header_row"),
                      "new_keywords": added, "keywords_total": len(items),
                      "volumes_are_ranges": ranged,
                      "note": ("Some volumes are ranges (the account has little ad spend); the lower end is used for "
                               "ranking.") if ranged else "",
                      "top_keywords": [{"keyword": x["keyword"], "monthly_searches": x["monthly_searches"]}
                                       for x in items[:12]]}, indent=2, ensure_ascii=False))


FILLER = STOP | set("and the for with from our are was has its his her you per into onto".split())
GENERIC = set(("men mens women womens woman man kid kids child children boy boys girl girls unisex adult adults "
               "size sizes small medium large xl xxl pack set sets piece pieces new black white grey gray blue red "
               "green pink brown navy beige cream gold silver yellow orange purple multi colour color one two three "
               "single double").split())


def toks(s):
    return {stem(w) for w in re.findall(r"[a-z0-9à-ÿ]+", (s or "").lower()) if len(w) >= 2 and w not in FILLER}


def product_tokens(p):
    parts = [p.get("title", ""), p.get("product_type", ""), p.get("google_product_category", "").split(">")[-1],
             p.get("category", ""), p.get("brand", ""), p.get("variant_label", "")]
    parts += list(p.get("attributes", {}).values())
    return toks(" ".join(parts))


def match_terms(ptoks, terms, limit, brand_toks=frozenset()):
    """Search terms that share a real product word with the product (a brand name alone doesn't count)."""
    anchors = {t for t in ptoks if t not in GENERIC and not t.isdigit() and t not in brand_toks}
    out = []
    for t in terms:
        tt = t.get("_toks")
        if tt is None:
            tt = t["_toks"] = toks(t["term"])
        if not tt or not (tt & anchors):
            continue
        # Recall over precision: a search term that names the product type is worth showing even when its other
        # words (slim, for men, waterproof) are not in the product data yet - those words are the opportunity.
        score = len(tt & ptoks) / float(len(tt))
        if score >= 0.3:
            out.append((score, t))
    out.sort(key=lambda x: (-(x[0] >= 0.99), -x[1]["impressions"], -x[1]["clicks"]))
    return [{"term": t["term"], "impressions": t["impressions"], "clicks": t["clicks"],
             "conversions": t["conversions"]} for s, t in out[:limit]]


def category_keywords(cat, ctoks, planner, limit, brand_toks=frozenset()):
    anchors = {t for t in ctoks if t not in GENERIC and not t.isdigit() and t not in brand_toks}
    out = []
    for k in planner:
        if cat in k.get("categories", []):
            out.append(k)
        elif not k.get("categories"):
            kt = k.get("_toks")
            if kt is None:
                kt = k["_toks"] = toks(k["keyword"])
            if kt & anchors and len(kt & ctoks) / float(len(kt) or 1) >= 0.5:
                out.append(k)
    out.sort(key=lambda k: -(k.get("monthly_searches") or 0))
    return [{"keyword": k["keyword"], "monthly_searches": k.get("monthly_searches"),
             "volume_text": k.get("volume_text", "")} for k in out[:limit]]


def load_run(run):
    p = run_paths(run)
    if not os.path.exists(p["products"]):
        sys.exit("No products.jsonl in %s - run `normalise` first." % run)
    cfg = read_cfg(run)
    products = read_jsonl(p["products"])
    drafts = {d["id"]: d for d in read_jsonl(p["drafts"])}
    return p, cfg, products, drafts


def load_research(p):
    if os.path.exists(p["research"]):
        with open(p["research"], encoding="utf-8") as f:
            return json.load(f)
    return {}


def cmd_categories(a):
    p, cfg, products, drafts = load_run(a.run)
    terms, planner, research = read_jsonl(p["terms"]), read_jsonl(p["planner"]), load_research(p)
    cats = {}
    for x in products:
        cats.setdefault(x["category"], []).append(x)
    total_clicks = sum(x.get("clicks", 0) for x in products)
    out = []
    for cat, items in sorted(cats.items(), key=lambda kv: (-sum(x.get("clicks", 0) for x in kv[1]), -len(kv[1]))):
        items_sorted = sorted(items, key=lambda x: -x.get("clicks", 0))
        ctoks = set()
        for x in items:
            ctoks |= product_tokens(x)
        clicks = sum(x.get("clicks", 0) for x in items)
        btoks = toks(" ".join([cfg.get("end_brand") or ""] + [x.get("brand", "") for x in items])) - \
            toks(cat)
        out.append({
            "category": cat, "products": len(items), "variant_groups": len({x["group"] for x in items}),
            "clicks": clicks if cfg.get("has_clicks") else None,
            "share_of_clicks": ("%d%%" % round(100.0 * clicks / total_clicks)) if total_clicks else None,
            "brands": sorted({x["brand"] for x in items if x.get("brand")})[:6],
            "top_products": [{"id": x["id"], "title": x["title"], "link": x.get("link", ""), "clicks": x.get("clicks")}
                             for x in items_sorted[:3]],
            "page_to_read": next((x["link"] for x in items_sorted if x.get("link")), ""),
            "search_terms": match_terms(ctoks, terms, 25, btoks) if terms else [],
            "keyword_planner": category_keywords(cat, ctoks, planner, 15, btoks) if planner else [],
            "research_saved": cat in research,
        })
    matched = set()
    if terms:
        for cat, items in cats.items():
            ctoks = set()
            for x in items:
                ctoks |= product_tokens(x)
            btoks = toks(" ".join([cfg.get("end_brand") or ""] + [x.get("brand", "") for x in items])) - toks(cat)
            matched |= {t["term"].lower() for t in match_terms(ctoks, terms, 10 ** 6, btoks)}
    unmatched = [{"term": t["term"], "impressions": t["impressions"], "clicks": t["clicks"]}
                 for t in terms if t["term"].lower() not in matched][:20]
    print(json.dumps({"store": cfg.get("store", ""), "brand_case": cfg.get("brand_case"),
                      "end_brand": cfg.get("end_brand"), "language": cfg.get("language"),
                      "search_terms_loaded": len(terms), "planner_keywords_loaded": len(planner),
                      "categories": out,
                      "unmatched_search_terms": unmatched,
                      "unmatched_note": ("Search terms that share no product word with any category. Some name a product "
                                         "in different words (a 'travel backpack' search for a daypack): give those to the "
                                         "products they fit. Ignore the rest.") if unmatched else ""},
                     indent=2, ensure_ascii=False))


def cmd_research(a):
    p, cfg, products, drafts = load_run(a.run)
    with open(a.notes_file, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    cats = {x["category"] for x in products}
    research = load_research(p)
    unknown = []
    for n in data:
        c = n.get("category")
        if not c:
            sys.exit("each note needs a 'category'")
        if c not in cats:
            unknown.append(c)
        n["saved"] = datetime.datetime.now().isoformat(timespec="seconds")
        research[c] = n
    with open(p["research"], "w", encoding="utf-8") as f:
        json.dump(research, f, indent=2, ensure_ascii=False)
    print(json.dumps({"saved": len(data), "categories_with_research": len(research),
                      "categories_without_research": sorted(cats - set(research)),
                      "unknown_categories": unknown}, indent=2, ensure_ascii=False))


def cmd_next(a):
    p, cfg, products, drafts = load_run(a.run)
    terms, planner, research = read_jsonl(p["terms"]), read_jsonl(p["planner"]), load_research(p)
    pending = [x for x in products if x["id"] not in drafts]
    batch = pending[: a.batch]
    if batch:
        last_group = batch[-1]["group"]
        for x in pending[a.batch: a.batch + 40]:
            if x["group"] == last_group:
                batch.append(x)
            else:
                break
    cats, cbrands = {}, {}
    for x in products:
        cats.setdefault(x["category"], set()).update(product_tokens(x))
        cbrands.setdefault(x["category"], set()).update(toks(x.get("brand", "")) - toks(x["category"]))
    end_toks = toks(cfg.get("end_brand") or "")
    out_products, out_cats = [], {}
    for x in batch:
        y = dict(x)
        y["description"] = (y.get("description") or "")[:400]
        btoks = (end_toks | toks(x.get("brand", ""))) - toks(x["category"])
        y["search_terms"] = match_terms(product_tokens(x), terms, 15, btoks) if terms else []
        out_products.append(y)
        c = x["category"]
        if c not in out_cats:
            r = research.get(c, {})
            out_cats[c] = {"keyword_planner": category_keywords(c, cats[c], planner, 15, (end_toks - toks(c)) | cbrands[c]) if planner else [],
                           "research": {k: v for k, v in r.items() if k not in ("category", "saved")}}
    print(json.dumps({"done": len(drafts), "total": len(products), "this_batch": len(batch),
                      "remaining_after_this_batch": len(pending) - len(batch),
                      "language": cfg.get("language", ""), "brand_case": cfg.get("brand_case"),
                      "end_brand": cfg.get("end_brand"),
                      "search_term_data": bool(terms), "keyword_planner_data": bool(planner),
                      "categories": out_cats, "products": out_products}, indent=2, ensure_ascii=False))


def validate_draft(d, ids):
    errs = []
    if not isinstance(d, dict):
        return ["draft is not an object"]
    if d.get("id") not in ids:
        errs.append("unknown id %r" % d.get("id"))
    if d.get("status") not in ("ready", "hold"):
        errs.append("status must be 'ready' or 'hold'")
    if d.get("status") == "ready" and not (d.get("title") or "").strip():
        errs.append("ready draft has no title")
    if d.get("status") == "hold" and not d.get("notes"):
        errs.append("hold draft needs notes explaining why")
    kws = d.get("keywords", [])
    if not isinstance(kws, list):
        errs.append("keywords must be a list")
    else:
        for k in kws:
            if not isinstance(k, dict) or not k.get("keyword") or k.get("source") not in SOURCES:
                errs.append("each keyword needs {keyword, source} with source one of: %s" % ", ".join(SOURCES))
                break
    return errs


def save_drafts(p, products, drafts):
    order = {x["id"]: i for i, x in enumerate(products)}
    write_jsonl(p["drafts"], sorted(drafts.values(), key=lambda d: order.get(d["id"], 10 ** 9)))


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
    lengths = {}
    for d in data:
        d["title"] = clean_title(d.get("title"))
        d.setdefault("keywords", [])
        d["saved"] = datetime.datetime.now().isoformat(timespec="seconds")
        drafts[d["id"]] = d
        lengths[d["id"]] = len(d["title"])
    save_drafts(p, products, drafts)
    print(json.dumps({"saved": len(data), "done": len(drafts), "total": len(products),
                      "remaining": len(products) - len(drafts),
                      "lengths": lengths,
                      "outside_130_150": {k: v for k, v in lengths.items() if v and not TARGET_MIN <= v <= TARGET_MAX}},
                     indent=2))


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

PRICEY = ["cheap", "cheapest", "affordable", "bargain", "budget", "discount"]


def source_blob(prod):
    parts = [prod.get("title", ""), prod.get("description", ""), prod.get("brand", ""), prod.get("product_type", ""),
             prod.get("google_product_category", ""), prod.get("variant_label", "")]
    parts += prod.get("highlights", [])
    parts += ["%s %s %s" % (d.get("section", ""), d.get("name", ""), d.get("value", "")) for d in prod.get("details", [])]
    parts += list(prod.get("attributes", {}).values())
    return " \n ".join(str(x) for x in parts if x)


def lint(prod, draft, all_drafts, cfg, search_vocab):
    E, W = [], []
    if draft.get("status") == "hold":
        return E, ["held - no new title; see notes"]
    t = draft.get("title") or ""
    low = t.lower()
    n = len(t)
    src = source_blob(prod)
    src_low = src.lower()
    end = cfg.get("end_brand") or ""
    if n > HARD_MAX:
        E.append("%d characters: over Google's 150 limit, and the end (where the brand sits) gets cut off" % n)
    elif n < SEEN:
        W.append("only %d characters: there is room for much more search language (aim for 130-150)" % n)
    elif n < TARGET_MIN and not draft.get("thin_data"):
        W.append("%d characters: aim for 130-150 (add the next-best keyword phrase)" % n)
    if "\t" in t or "\n" in t or "\r" in t:
        E.append("contains a tab or line break")
    if t.startswith('"'):
        E.append("starts with a double quote (breaks some feed parsers)")
    elif '"' in t:
        W.append('contains a double quote: write 12 Inch rather than 12"')
    if re.search(r"<[a-zA-Z/][^>]*>", t):
        E.append("contains HTML")
    if "!" in t:
        E.append("exclamation mark (Google treats it as promotional)")
    if EMOJI.search(t) or BULLETS.search(t):
        E.append("emoji or decorative symbol")
    if LINK.search(t):
        E.append("contains a web address: %s" % LINK.search(t).group(0))
    if PRICE.search(t):
        E.append("contains a price or currency: %s" % PRICE.search(t).group(0))
    m = TITLE_PROMO.search(t) or TIME_TEXT.search(t)
    if m:
        E.append("promotional, shipping or time-related wording: '%s'" % m.group(0))
    m = SOFT_PROMO_T.search(t)
    if m and not re.search(re.escape(m.group(0)), src, re.I):
        W.append("'%s' reads as promotion: keep it only if the product data says it and people search it" % m.group(0))
    secs = sections(t)
    if any(not s for s in secs):
        E.append("empty section: a doubled pipe, or a pipe at the start or end")
    if len(secs) > 8:
        W.append("%d sections: merge overlapping phrases (3-8 is normal)" % len(secs))
    if len(secs) == 1 and n > SEEN:
        W.append("no sections: separate the keyword phrases with |")
    # a section whose phrase already appears, in the same word order, inside another section wastes space
    def seq(x):
        return [stem(w) for w in re.findall(r"[a-z0-9à-ÿ]+", x.lower()) if w not in FILLER]
    st = [(s, seq(s)) for s in secs if s]
    for i, (s1, q1) in enumerate(st):
        for j, (s2, q2) in enumerate(st):
            if i == j or len(q1) < 2 or len(q1) > len(q2) or (q1 == q2 and i < j):
                continue
            if any(q2[k:k + len(q1)] == q1 for k in range(len(q2) - len(q1) + 1)):
                W.append("section '%s' repeats a phrase already in '%s': merge them and spend the space on a new phrase" % (s1, s2))
                break
    # numbers must come from the product's data
    src_nums = {norm_num(x) for x in NUM.findall(src)}
    bad = sorted({x for x in NUM.findall(t) if norm_num(x) not in src_nums})
    if bad:
        E.append("number(s) not in this product's data: %s (titles may only state numbers the data contains)" % ", ".join(bad))
    # brand rules
    if end:
        last = re.sub(r"[®™]", "", secs[-1]).strip()
        if not same_name(last, end) or len(re.sub(r"[^a-z0-9]", "", last.lower())) > len(re.sub(r"[^a-z0-9]", "", end.lower())) + 2:
            E.append("the last section must be the brand '%s' (it is '%s')" % (end, secs[-1]))
        vvals = [v for v in list(prod.get("variant_parts", [])) + [prod.get("attributes", {}).get(k, "")
                 for k in ("color", "size", "material", "pattern", "style")] if v]

        def without_variants(x):
            for v in sorted(vvals, key=len, reverse=True):
                x = re.sub(re.escape(v), " ", x, flags=re.I)
            return x
        if any(end.lower() in without_variants(s).lower() for s in secs[:-1] if s):
            W.append("'%s' also appears before the last section: keep the front for words people search" % end)
    store = cfg.get("store") or ""
    if not end and store and not same_name(store, prod.get("brand", "")) and store.lower() in low:
        W.append("the store's name '%s' is in the title: Google's title rules say not to add your company's name "
                 "(keep it only if the user asked for it)" % store)
    pb = prod.get("brand", "")
    if needs_product_brand(pb, cfg.get("brand_case"), end):
        i = low.find(pb.lower())
        if i < 0:
            E.append("product brand '%s' is missing: for brands you resell, it goes in the first half" % pb)
        elif i > n / 2:
            E.append("product brand '%s' is in the second half: move it into the first or second section" % pb)
    # variants
    parts = [x for x in prod.get("variant_parts", []) if x]
    if prod.get("group_size", 1) > 1 and parts:
        missing = [x for x in parts if variant_pos(x, t) < 0]
        if missing:
            E.append("variant not named: %s (copy it exactly from the original title or attributes)" % ", ".join(missing))
    # duplicates
    dupes = [d["id"] for d in all_drafts if d["id"] != draft["id"] and d.get("status") == "ready"
             and (d.get("title") or "").lower() == low]
    if dupes:
        E.append("identical to the title for: %s" % ", ".join(dupes[:5]))
    # wording
    caps = sorted({w for w in caps_words(t) if w not in src})
    # one short capitalised word is usually an abbreviation (RFID, USB); several, or a long one, is shouting
    if len(caps) >= 2 or any(len(w) >= 6 for w in caps):
        W.append("capitals not in the product data (Google: no capitals for emphasis): %s" % ", ".join(caps))
    vocab = search_vocab + " " + " ".join(k.get("keyword", "") for k in draft.get("keywords", [])
                                          if k.get("source") in ("search_terms", "keyword_planner")).lower()
    for wl, why in ((SUPERLATIVES, "superlative"), (PRICEY, "price word")):
        hits = [w for w in wl if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), low)
                and not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), src_low)
                and not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), vocab)]
        if hits:
            W.append("%s not in the product data or the search data: %s (keep it only if people search it)" % (why, ", ".join(hits)))
    hl = [w for w in HEALTH if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(w), low)]
    if hl:
        W.append("health wording: %s - Google limits health claims; keep it only if the product data supports it" % ", ".join(hl))
    lang_l = (cfg.get("language") or "").lower()
    pairs = [(us, gb) for us, gb in SPELL] if lang_l in GB_LIKE else [(gb, us) for us, gb in SPELL] if lang_l == "en-us" else []
    wrong = [w for w, _ in pairs if re.search(r"\b%s\b" % w, low) and not re.search(r"\b%s\b" % w, prod.get("title", "").lower())]
    if wrong:
        W.append("spelling for %s: %s" % (cfg.get("language"), ", ".join(wrong)))
    ow = {stem(w): w for w in words(prod.get("title", "")) if len(w) >= 4 and w.lower() not in FILLER}
    if len(ow) >= 4:
        nw = {stem(w) for w in words(t)}
        gone = [v for k, v in ow.items() if k not in nw]
        if len(gone) / float(len(ow)) > 0.6:
            W.append("most words of the original title are gone (%s): check the product is still named correctly" % ", ".join(gone[:8]))
    return E, W


def run_check(run):
    p, cfg, products, drafts = load_run(run)
    pmap = {x["id"]: x for x in products}
    vocab = " ".join([t["term"] for t in read_jsonl(p["terms"])] + [k["keyword"] for k in read_jsonl(p["planner"])]).lower()
    dl = list(drafts.values())
    report = {}
    for d in dl:
        if d["id"] not in pmap:
            report[d["id"]] = {"errors": ["title for an id that is not in products.jsonl"], "warnings": []}
            continue
        e, w = lint(pmap[d["id"]], d, dl, cfg, vocab)
        report[d["id"]] = {"errors": e, "warnings": w}
    with open(p["report"], "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return p, cfg, products, drafts, report


def cmd_check(a):
    p, cfg, products, drafts, report = run_check(a.run)
    errs = {k: v["errors"] for k, v in report.items() if v["errors"]}
    warns = {k: v["warnings"] for k, v in report.items() if v["warnings"]}
    print(json.dumps({"titles": len(drafts), "products": len(products), "not_written_yet": len(products) - len(drafts),
                      "with_errors": len(errs), "with_warnings": len(warns), "errors": errs, "warnings": warns,
                      "report_file": p["report"]}, indent=2, ensure_ascii=False))
    if errs:
        sys.exit(1)


# ---------------------------------------------------------------------------
# A small .xlsx writer (standard library only)
# ---------------------------------------------------------------------------

XML_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def xesc(s):
    return XML_BAD.sub("", html.escape(str(s), quote=False))


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, sheets):
    """sheets: [{name, headers, rows, widths, text_cols, wrap_cols, len_col (index whose cells are =LEN(col))}].
    A row cell may be ("len", source_col_index, cached_value) for a live character count."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' \
         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for i in range(len(sheets)):
        ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1))
    ct.append("</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wb_sheets, wb_rels, names = [], [], []
    for i, s in enumerate(sheets):
        wb_sheets.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (xesc(s["name"]), i + 1, i + 1))
        wb_rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1))
        last = "%s%d" % (col_letter(len(s["headers"]) - 1), len(s["rows"]) + 1)
        names.append('<definedName name="_xlnm._FilterDatabase" localSheetId="%d" hidden="1">\'%s\'!$A$1:$%s$%d</definedName>'
                     % (i, xesc(s["name"]), col_letter(len(s["headers"]) - 1), len(s["rows"]) + 1))
        s["_ref"] = "A1:" + last
    wb_rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (len(sheets) + 1))
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook %s><sheets>%s</sheets>'
                '<definedNames>%s</definedNames><calcPr calcId="0" fullCalcOnLoad="1"/></workbook>'
                % (ns, "".join(wb_sheets), "".join(names)))
    wbrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
              % "".join(wb_rels))
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
              '<fill><patternFill patternType="solid"><fgColor rgb="FF1A1A1A"/><bgColor indexed="64"/></patternFill></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="4">'
              '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top"/></xf>'
              '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center"/></xf>'
              '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>'
              '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
              '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
              '<dxfs count="1"><dxf><font><b/><color rgb="FF9C0006"/></font><fill><patternFill><bgColor rgb="FFFFC7CE"/></patternFill></fill></dxf></dxfs>'
              '</styleSheet>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wbrels)
        z.writestr("xl/styles.xml", styles)
        for i, s in enumerate(sheets):
            text_cols, wrap_cols = set(s.get("text_cols", [])), set(s.get("wrap_cols", []))
            out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet %s>' % ns,
                   '<sheetViews><sheetView workbookViewId="0"%s><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                   % (' tabSelected="1"' if i == 0 else ""),
                   '<sheetFormatPr defaultRowHeight="15"/><cols>']
            for c, w in enumerate(s["widths"]):
                out.append('<col min="%d" max="%d" width="%s" customWidth="1"/>' % (c + 1, c + 1, w))
            out.append("</cols><sheetData>")
            out.append('<row r="1">%s</row>' % "".join(
                '<c r="%s1" t="inlineStr" s="1"><is><t>%s</t></is></c>' % (col_letter(c), xesc(h)) for c, h in enumerate(s["headers"])))
            for r, row in enumerate(s["rows"], start=2):
                cells = []
                for c, v in enumerate(row):
                    ref = "%s%d" % (col_letter(c), r)
                    if isinstance(v, tuple) and v and v[0] == "len":
                        cells.append('<c r="%s"><f>LEN(%s%d)</f><v>%d</v></c>' % (ref, col_letter(v[1]), r, v[2]))
                    elif isinstance(v, (int, float)) and not isinstance(v, bool) and c not in text_cols:
                        cells.append('<c r="%s"><v>%s</v></c>' % (ref, v))
                    elif v is None or v == "":
                        continue
                    else:
                        st = 2 if c in text_cols else (3 if c in wrap_cols else 0)
                        cells.append('<c r="%s" t="inlineStr" s="%d"><is><t xml:space="preserve">%s</t></is></c>' % (ref, st, xesc(v)))
                out.append('<row r="%d">%s</row>' % (r, "".join(cells)))
            out.append("</sheetData>")
            out.append('<autoFilter ref="%s"/>' % s["_ref"])
            if s.get("len_col") is not None and s["rows"]:
                lc = col_letter(s["len_col"])
                out.append('<conditionalFormatting sqref="%s2:%s%d"><cfRule type="cellIs" dxfId="0" priority="1" operator="notBetween">'
                           '<formula>%d</formula><formula>%d</formula></cfRule></conditionalFormatting>'
                           % (lc, lc, len(s["rows"]) + 1, TARGET_MIN, TARGET_MAX))
            out.append("</worksheet>")
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), "".join(out))


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def out_names(cfg):
    slug = slugify(cfg.get("store") or cfg.get("end_brand") or "store")
    return slug, "%s-supplemental-titles.tsv" % slug, "%s-title-review.xlsx" % slug, "%s-title-review.html" % slug


def title_html(t):
    return '<span class="sep">|</span>'.join(esc(s.strip()) for s in t.split("|"))


def build_outputs(run, force):
    p, cfg, products, drafts, report = run_check(run)
    errs = {k: v["errors"] for k, v in report.items() if v["errors"]}
    if errs and not force:
        return {"built": False, "reason": "fix the errors first (or --force, which holds those products back)",
                "errors": errs}
    slug, tsv_name, xlsx_name, html_name = out_names(cfg)
    pmap = {x["id"]: x for x in products}
    order = {x["id"]: i for i, x in enumerate(products)}
    ready = sorted([d for d in drafts.values() if d.get("status") == "ready" and d["id"] in pmap and not errs.get(d["id"])],
                   key=lambda d: order[d["id"]])
    held = [d for d in drafts.values() if d.get("status") == "hold"]
    terms, planner, research = read_jsonl(p["terms"]), read_jsonl(p["planner"]), load_research(p)
    tmap = {t["term"].lower(): t for t in terms}
    kmap = {k["keyword"].lower(): k for k in planner}

    # 1. Supplemental feed (tab-separated, UTF-8, no BOM)
    tsv = os.path.join(run, tsv_name)
    with open(tsv, "w", encoding="utf-8", newline="") as f:
        f.write("id\ttitle\tstructured_title\n")
        for d in ready:
            f.write("%s\t%s\t%s\n" % (d["id"], d["title"], structured(d["title"])))
    with open(tsv, encoding="utf-8") as f:
        body = [ln for ln in f.read().split("\n")[1:] if ln]
    assert all(ln.count("\t") == 2 for ln in body), "TSV row with the wrong number of columns"
    ids = [ln.split("\t")[0] for ln in body]
    assert len(ids) == len(set(ids)), "duplicate id in TSV"
    assert set(ids) <= set(pmap), "TSV id not in the input products"
    assert all(len(ln.split("\t")[1]) <= HARD_MAX for ln in body), "title over 150 characters in TSV"

    # 2. Review workbook
    has_clicks = bool(cfg.get("has_clicks"))
    trows = []
    for x in products:
        d = drafts.get(x["id"], {})
        new = d.get("title", "") if d.get("status") == "ready" else ""
        note = "; ".join(([d["notes"]] if d.get("notes") else []) +
                         report.get(x["id"], {}).get("errors", []) + report.get(x["id"], {}).get("warnings", []))
        if d.get("status") == "hold":
            note = "Held: " + (d.get("notes") or "")
        elif not d:
            note = "Not written yet"
        row = [x["id"], x["title"], new, ("len", 2, len(new)),
               "; ".join("%s (%s)" % (k["keyword"], SOURCE_NAMES.get(k["source"], k["source"])) for k in d.get("keywords", []))]
        if has_clicks:
            row.append(x.get("clicks", 0))
        row.append(note)
        trows.append(row)
    theaders = ["Product ID", "Original title", "New title", "Characters", "Keywords targeted"] + \
               (["Clicks"] if has_clicks else []) + ["Notes"]
    rrows = []
    for cat in sorted({x["category"] for x in products}):
        r = research.get(cat, {})
        rrows.append([cat, sum(1 for x in products if x["category"] == cat), r.get("summary", ""), r.get("audience", ""),
                      "; ".join(r.get("benefits", [])) if isinstance(r.get("benefits"), list) else r.get("benefits", ""),
                      r.get("positioning", ""), "; ".join(r.get("pages", []) or [])])
    krows = []
    for d in ready:
        for k in d.get("keywords", []):
            kw = k["keyword"]
            pk, tk = kmap.get(kw.lower(), {}), tmap.get(kw.lower(), {})
            krows.append([d["id"], pmap[d["id"]]["title"], kw, SOURCE_NAMES.get(k["source"], k["source"]),
                          pk.get("monthly_searches") if pk.get("monthly_searches") is not None else "",
                          tk.get("impressions", ""), tk.get("clicks", "")])
    xlsx = os.path.join(run, xlsx_name)
    write_xlsx(xlsx, [
        {"name": "Titles", "headers": theaders, "rows": trows, "text_cols": [0],
         "widths": [22, 60, 70, 11, 60] + ([9] if has_clicks else []) + [60], "len_col": 3},
        {"name": "Research", "headers": ["Category", "Products", "What they are", "Who they're for", "Key benefits",
                                          "How the store positions them", "Pages read"],
         "rows": rrows, "widths": [28, 10, 50, 40, 50, 40, 50], "wrap_cols": [2, 3, 4, 5, 6]},
        {"name": "Keywords", "headers": ["Product ID", "Product title", "Keyword", "Source", "Monthly searches",
                                          "Search term impressions", "Search term clicks"],
         "rows": krows, "text_cols": [0], "widths": [22, 50, 40, 22, 16, 22, 18]},
    ])

    # 3. Review page
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    total = len(products)
    ob = [len(pmap[d["id"]]["title"]) for d in ready]
    na = [len(d["title"]) for d in ready]
    avg_b = round(sum(ob) / len(ob)) if ob else 0
    avg_a = round(sum(na) / len(na)) if na else 0
    src_counts = {s: 0 for s in SOURCES}
    st_used = set()
    for d in ready:
        for k in d.get("keywords", []):
            src_counts[k["source"]] = src_counts.get(k["source"], 0) + 1
            if k["source"] == "search_terms":
                st_used.add(k["keyword"].lower())
    checks = [k for k, v in report.items() if v["warnings"] and drafts.get(k, {}).get("status") == "ready"]
    content = ['<div class="stat-row">',
               '<div class="stat-card"><div class="num">%d</div><div class="lbl">new titles ready to upload%s</div></div>'
               % (len(ready), (" (of %d products)" % total) if len(ready) != total else ""),
               '<div class="stat-card"><div class="num">%s&rarr;%s</div><div class="lbl">average characters, before &rarr; after (Google allows 150)</div></div>' % (avg_b, avg_a)]
    if terms:
        content.append('<div class="stat-card"><div class="num">%d</div><div class="lbl">of your real search terms now in the titles</div></div>' % len(st_used))
    else:
        kw_avg = (sum(len(d.get("keywords", [])) for d in ready) / float(len(ready))) if ready else 0
        content.append('<div class="stat-card"><div class="num">%.1f</div><div class="lbl">keyword phrases targeted per title</div></div>' % kw_avg)
    content.append('<div class="stat-card%s"><div class="num">%d</div><div class="lbl">titles to check before you upload</div></div>'
                   % (" hot" if checks or held or errs else "", len(checks) + len(held) + len(errs)))
    content.append("</div>")
    items = [(lbl, sum(1 for x in products if k in x.get("original_flags", []))) for k, lbl in FLAG_NAMES]
    items = [(l, c) for l, c in items if c]
    if items:
        content.append('<div class="viz-card"><div class="viz-title">What was wrong with the original titles</div>%s'
                       '<div class="viz-note">Counted across the %d products in this run. In Google Shopping the title does the job '
                       'keywords do in a search campaign: words that are not in it are searches the product is unlikely to show for.</div></div>'
                       % (bar_rows(items, total), total))
    rows = [(pmap[d["id"]], d) for d in ready][:40]
    if rows:
        mx = 160

        def pos(v):
            return round(100.0 * min(v, mx) / mx, 2)
        dl = []
        for prod, d in rows:
            b, af = len(prod["title"]), len(d["title"])
            lo, hi = sorted((b, af))
            label = prod["title"] if len(prod["title"]) <= 46 else prod["title"][:45].rstrip() + "…"
            dl.append('<div class="db-row"><span class="db-label" title="%s">%s</span><span class="db-track">'
                      '<span class="db-line" style="left:%s%%;width:%s%%"></span>'
                      '<span class="db-dot before" style="left:%s%%" title="before: %d"></span>'
                      '<span class="db-dot after" style="left:%s%%" title="after: %d"></span></span>'
                      '<span class="db-val">%d &rarr; %d</span></div>'
                      % (esc(prod["id"]), esc(label), pos(lo), pos(hi) - pos(lo), pos(b), b, pos(af), af, b, af))
        content.append('<div class="viz-card"><div class="viz-title">Title length, before and after (characters)</div>'
                       '<div class="db-legend"><span><i class="db-dot-key before"></i>Before</span><span><i class="db-dot-key after"></i>After</span>'
                       '<span class="guide-key"><i class="db-band-key"></i>Target 130&ndash;150</span><span class="guide-key"><i class="db-mark-key"></i>Shoppers usually see about the first 70</span></div>'
                       '<div class="db-wrap"><div class="db-guides"><span class="db-band" style="left:%s%%;width:%s%%"></span><span class="db-mark" style="left:%s%%"></span></div>%s</div>'
                       '<div class="viz-note">Scale 0&ndash;%d characters. Google reads every word of the title for matching, even the part shoppers don\'t see.%s</div></div>'
                       % (pos(TARGET_MIN), pos(TARGET_MAX) - pos(TARGET_MIN), pos(SEEN), "\n".join(dl), mx,
                          (" Showing the first 40 of %d." % len(ready)) if len(ready) > 40 else ""))
    src_items = [(SOURCE_NAMES[s], c) for s, c in src_counts.items() if c]
    if src_items:
        allk = sum(c for _, c in src_items)
        content.append('<div class="viz-card"><div class="viz-title">Where the targeted keywords came from</div>%s'
                       '<div class="viz-note">%d keyword phrases across %d titles. Your own search terms are the strongest evidence: '
                       'they are what shoppers typed before they saw your products.</div></div>'
                       % (bar_rows(src_items, allk, "pos"), allk, len(ready)))

    # Section 01 - check these first
    sec = 1
    content.append('<div class="section"><div class="section-head"><span class="eyebrow">Section %02d</span><h2>Check these first</h2>'
                   '<p>What the titles were built from, and anything worth a second look before you upload.</p></div>' % sec)
    facts = []
    facts.append("<li><strong>Search terms:</strong> %s</li>" % (
        "%d loaded from your Google Ads data; %d of them made it into the titles." % (len(terms), len(st_used)) if terms else
        "none were used. The titles rest on your product pages, Keyword Planner (if used) and judgement. Add a search terms "
        "report and rerun to make them stronger."))
    facts.append("<li><strong>Keyword Planner:</strong> %s</li>" % (
        "%d keyword ideas with search volumes." % len(planner) if planner else "not used."))
    facts.append("<li><strong>Brand:</strong> %s</li>" % (
        "your brand <em>%s</em> ends every title, so the front stays free for the words people search." % esc(cfg["end_brand"])
        if cfg.get("end_brand") else
        "each product's own brand sits in the first half of its title. Your store name is not added, because Google's "
        "title rules say not to add your company's name." if cfg.get("brand_case") == "reseller" else
        "no brand name is added at the end."))
    facts.append("<li><strong>Research:</strong> %d of %d categories have saved notes (see the Research tab of the workbook).</li>"
                 % (len([c for c in research if c in {x['category'] for x in products}]), len({x["category"] for x in products})))
    content.append('<div class="note-card"><ul class="facts">%s</ul></div>' % "".join(facts))
    if checks:
        trs = ["<tr><td>%s<div class=\"ids\">%s</div></td><td>%s</td></tr>"
               % (esc(pmap[k]["title"]), esc(k), "<br>".join(esc(w) for w in report[k]["warnings"]))
               for k in sorted(checks, key=lambda k: order.get(k, 0))]
        content.append('<div class="tbl-wrap"><table><thead><tr><th>Product</th><th>Worth a look</th></tr></thead><tbody>%s</tbody></table></div>'
                       % "\n".join(trs))
    if held or errs:
        lis = ["<li><strong>%s</strong> %s &mdash; %s</li>" % (esc(pmap.get(d["id"], {}).get("title", "")), esc(d["id"]), esc(d.get("notes")))
               for d in held]
        lis += ["<li><strong>%s</strong> %s &mdash; still has errors: %s</li>" % (esc(pmap.get(k, {}).get("title", "")), esc(k), esc("; ".join(v)))
                for k, v in errs.items()]
        content.append('<div class="avoid"><h3>Held back &mdash; not in the supplemental feed</h3><ul>%s</ul></div>' % "".join(lis))
    content.append("</div>")

    # Section 02 - before and after
    sec += 1
    content.append('<div class="section"><div class="section-head"><span class="eyebrow">Section %02d</span><h2>Before and after</h2>'
                   '<p>Every new title, in feed order. The keywords under each title are the search phrases it was built to match.</p></div>' % sec)
    used = [s for s in SOURCES if src_counts.get(s)]
    if used:
        content.append('<div class="kw-legend">Keyword sources: %s</div>'
                       % " ".join('<span class="kw kw-%s">%s</span>' % (s, esc(SOURCE_NAMES[s])) for s in used))
    for d in ready:
        prod = pmap[d["id"]]
        chips = "".join('<span class="kw kw-%s" title="%s">%s</span>' % (k["source"], esc(SOURCE_NAMES.get(k["source"], "")), esc(k["keyword"]))
                        for k in d.get("keywords", []))
        meta = ["Check: %s" % esc(w) for w in report.get(d["id"], {}).get("warnings", [])]
        if d.get("edited"):
            meta.insert(0, "Edited by you")
        if d.get("notes"):
            meta.append(esc(d["notes"]))
        perf = ""
        if has_clicks:
            perf = '<span class="ba-perf">%s clicks in the data</span>' % "{:,}".format(prod.get("clicks", 0))
        content.append(
            '<div class="ba-card"><div class="ba-head"><div><span class="ba-id">%s</span>%s</div><span class="ba-cat">%s</span></div>'
            '<div class="ba-row before"><span class="ba-lbl">Before &middot; %d characters</span><p>%s</p></div>'
            '<div class="ba-row after"><span class="ba-lbl">After &middot; %d characters</span><p>%s</p></div>'
            '%s%s</div>'
            % (esc(d["id"]), perf, esc(prod.get("category", "")), len(prod["title"]), esc(prod["title"]) or "<em>No title</em>",
               len(d["title"]), title_html(d["title"]),
               ('<div class="kws">%s</div>' % chips) if chips else "",
               ('<ul class="ba-meta">%s</ul>' % "".join("<li>%s</li>" % m for m in meta)) if meta else ""))
    content.append("</div>")

    out_html = tpl
    rep = {"{{STORE}}": esc(cfg.get("store") or cfg.get("end_brand") or "Your store"), "{{DATE}}": datetime.date.today().isoformat(),
           "{{LANG}}": esc(cfg.get("language") or "not set"), "{{COUNT}}": str(len(ready)), "{{TSV_NAME}}": esc(tsv_name),
           "{{XLSX_NAME}}": esc(xlsx_name), "{{SEC_NEXT}}": "%02d" % (sec + 1), "<!--{{CONTENT}}-->": "\n".join(content)}
    for k, v in rep.items():
        out_html = out_html.replace(k, v)
    out_html = re.sub(r"<!--\s*Component reference.*?-->\s*", "", out_html, flags=re.S)
    htmlp = os.path.join(run, html_name)
    with open(htmlp, "w", encoding="utf-8") as f:
        f.write(out_html)
    return {"built": True, "supplemental_feed": os.path.abspath(tsv), "rows": len(ready),
            "review_workbook": os.path.abspath(xlsx), "review_page": os.path.abspath(htmlp),
            "held_back": [d["id"] for d in held] + list(errs), "titles_with_warnings": len(checks),
            "not_written_yet": len(products) - len(drafts)}


def cmd_build(a):
    res = build_outputs(a.run, a.force)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res["built"]:
        sys.exit(1)


def cmd_apply(a):
    p, cfg, products, drafts = load_run(a.run)
    headers, rows, meta = table_rows(a.file, {"product_id"}, sheet_name="Titles")
    if "product_id" not in headers or "new_title" not in headers:
        sys.exit("Expected 'Product ID' and 'New title' columns (the Titles tab of the review workbook). Found: %s"
                 % ", ".join(headers))
    ids = {x["id"] for x in products}
    changed, unknown, cleared = [], [], []
    for r in rows:
        pid = first(r, "product_id")
        new = clean_title(first(r, "new_title"))
        if pid not in ids:
            if pid:
                unknown.append(pid)
            continue
        d = drafts.get(pid)
        if not new:
            if d and d.get("status") == "ready":
                cleared.append(pid)
            continue
        if not d or d.get("title") != new or d.get("status") != "ready":
            d = d or {"id": pid, "keywords": []}
            nt = toks(new)
            d["keywords"] = [k for k in d.get("keywords", []) if toks(k.get("keyword", "")) <= nt]
            d.update({"title": new, "status": "ready", "edited": True,
                      "saved": datetime.datetime.now().isoformat(timespec="seconds")})
            drafts[pid] = d
            changed.append(pid)
    for pid in cleared:
        drafts[pid].update({"status": "hold", "notes": "title cleared in the review workbook", "edited": True})
    save_drafts(p, products, drafts)
    res = build_outputs(a.run, a.force)
    rep_file = run_paths(a.run)["report"]
    checks = {}
    if os.path.exists(rep_file):
        with open(rep_file, encoding="utf-8") as f:
            full = json.load(f)
        checks = {k: full[k] for k in changed if k in full and (full[k]["errors"] or full[k]["warnings"])}
    res.update({"edits_applied": len(changed), "edited_ids": changed[:50], "cleared_and_held": cleared,
                "checks_on_edited_titles": checks,
                "unknown_ids_in_file": unknown[:20],
                "note": "IDs in the file that match no product were ignored; check they were not retyped." if unknown else ""})
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res["built"]:
        sys.exit(1)


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inspect")
    s.add_argument("feed")
    s.add_argument("--perf", help="a product performance report (item ID + clicks) to rank products")
    s.add_argument("--store", default="")
    s.add_argument("--id-col", default="")
    s.add_argument("--lang", default="")
    s.set_defaults(fn=cmd_inspect)
    s = sub.add_parser("normalise", aliases=["normalize"])
    s.add_argument("feed")
    s.add_argument("--run", required=True)
    s.add_argument("--perf", help="a product performance report (item ID + clicks)")
    s.add_argument("--top", type=int, help="the N products with the most clicks")
    s.add_argument("--pick", action="append", help="an ID, product URL or title (repeatable)")
    s.add_argument("--pick-file", help="text file, one ID / URL / title per line")
    s.add_argument("--first", type=int)
    s.add_argument("--all", action="store_true")
    s.add_argument("--no-variants", action="store_true", help="do not pull in the other variants of a chosen product")
    s.add_argument("--store", default="", help="the store's name")
    s.add_argument("--brand-case", choices=["own", "reseller"], default="", help="override: only when the user says")
    s.add_argument("--end-brand", default="", help="override: the name that ends every title")
    s.add_argument("--no-end-brand", action="store_true", help="override: end titles without a brand name")
    s.add_argument("--id-col", default="", help="override: only when the user names the item ID column")
    s.add_argument("--id-from-rest", action="store_true", help="force stripping online:en:US: prefixes (normally automatic)")
    s.add_argument("--lang", default="", help="override: only when the user states a language/spelling, e.g. en-GB")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_normalise)
    s = sub.add_parser("terms")
    s.add_argument("file")
    s.add_argument("--run", required=True)
    s.add_argument("--label", default="", help="a short name for where these terms came from")
    s.add_argument("--replace", action="store_true", help="drop terms loaded earlier")
    s.set_defaults(fn=cmd_terms)
    s = sub.add_parser("planner")
    s.add_argument("file")
    s.add_argument("--run", required=True)
    s.add_argument("--category", default="", help="the category these ideas were requested for")
    s.set_defaults(fn=cmd_planner)
    s = sub.add_parser("categories")
    s.add_argument("--run", required=True)
    s.set_defaults(fn=cmd_categories)
    s = sub.add_parser("research")
    s.add_argument("--run", required=True)
    s.add_argument("notes_file")
    s.set_defaults(fn=cmd_research)
    s = sub.add_parser("next")
    s.add_argument("--run", required=True)
    s.add_argument("--batch", type=int, default=20)
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
    s = sub.add_parser("apply")
    s.add_argument("file")
    s.add_argument("--run", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_apply)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
