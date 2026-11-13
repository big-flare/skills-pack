#!/usr/bin/env python3
"""Google Ads Audit Analysis helper. Plain Python 3.8+, standard library only, nothing to install.

Turns a Google Ads account's data into an audit workbook (.xlsx) that opens in Google Sheets or Excel:
Start Here, Account, Search Volume (optional), Channel Split, Campaign, Assets, Products, Product Families,
Product Mapping and Keyword Gap tabs, with live dropdowns, editable thresholds and charts.

Commands (run them from the user's working directory; RUN is the run folder, e.g. loma-audit):

  script   --from YYYY-MM-DD --to YYYY-MM-DD [--customer-id ID] [--out FILE]
           Write the read-only Google Ads Script with the dates filled in (for users without a connection).
  load     SOURCE --run RUN [--account-name NAME --customer-id ID --currency CODE --from D --to D] [--force]
           Read the data: the file the Google Ads Script saved, or a folder of query results saved from a
           Google Ads connection (one file per query, named after it: campaigns_daily.json, ...).
  families --run RUN [--write]
           Suggest product families (the Product Families tab) and save them to RUN/product-families.csv.
  planner  FILE --run RUN [--market "United Kingdom"] [--language English]
           Read Keyword Planner monthly search volumes (a Keyword Planner download, or saved connection
           results) for the Search Volume tab.
  build    --run RUN --store "Store name" [--domain example.com] [--margin 0.5] [--roas 4] [--cost 50]
           [--family-roas 4] [--family-cost 100] [--currency-symbol "£"] [--out FILE]
           Build the workbook and print the headline numbers.

Every command prints JSON. Errors exit with a message that says what to fix.
"""

import argparse
import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
from collections import defaultdict, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsxlite import (Workbook, Text, col_letter, ref, rng, quote_sheet,  # noqa: E402
                      doughnut_chart, stacked_bar_chart, line_chart)

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
PACK_URL = "https://github.com/big-flare/skills-pack"
BF_URL = "https://bigflare.com"

# ---------------------------------------------------------------------------------------------
# Google Ads enums. Connections return names ("SEARCH"); some return numbers. Map both.
# ---------------------------------------------------------------------------------------------
NETWORK = {2: "SEARCH", 3: "SEARCH_PARTNERS", 4: "CONTENT", 5: "YOUTUBE_SEARCH", 6: "YOUTUBE_WATCH", 7: "MIXED",
           8: "YOUTUBE", 10: "GOOGLE_OWNED_CHANNELS", 11: "GMAIL", 12: "DISCOVER", 13: "MAPS"}
KNOWN_NETWORKS = {"SEARCH", "SEARCH_PARTNERS", "CONTENT", "YOUTUBE", "YOUTUBE_SEARCH", "YOUTUBE_WATCH", "GMAIL",
                  "DISCOVER", "MAPS", "MIXED"}
CHANNEL_TYPE = {2: "SEARCH", 3: "DISPLAY", 4: "SHOPPING", 5: "HOTEL", 6: "VIDEO", 7: "MULTI_CHANNEL", 8: "LOCAL",
                9: "SMART", 10: "PERFORMANCE_MAX", 11: "LOCAL_SERVICES", 13: "TRAVEL", 14: "DEMAND_GEN"}
TYPE_LABEL = {"PERFORMANCE_MAX": "Performance Max", "SHOPPING": "Shopping", "SEARCH": "Search", "DISPLAY": "Display",
              "VIDEO": "Video", "DEMAND_GEN": "Demand Gen", "DISCOVERY": "Demand Gen", "SMART": "Smart",
              "LOCAL": "Local", "MULTI_CHANNEL": "App", "HOTEL": "Hotel", "TRAVEL": "Travel"}
ASSET_FIELD = {2: "HEADLINE", 3: "DESCRIPTION", 7: "MARKETING_IMAGE", 17: "LONG_HEADLINE", 18: "SQUARE_MARKETING_IMAGE",
               19: "YOUTUBE_VIDEO", 20: "PORTRAIT_MARKETING_IMAGE"}
ASSET_SOURCE = {2: "Advertiser", 3: "Automatically created", 4: "Automatically created"}
IMAGE_FIELDS = {"MARKETING_IMAGE", "SQUARE_MARKETING_IMAGE", "PORTRAIT_MARKETING_IMAGE", "TALL_PORTRAIT_MARKETING_IMAGE",
                "VERTICAL_MARKETING_IMAGE"}
PRODUCT_STATUS = {1: "Unknown", 2: "Not eligible", 3: "Eligible (limited)", 4: "Eligible"}
ENTITY_STATUS = {2: "ENABLED", 3: "PAUSED", 4: "REMOVED"}
PRIMARY_STATUS = {2: "ELIGIBLE", 3: "PAUSED", 4: "REMOVED", 5: "PENDING", 6: "NOT_ELIGIBLE", 7: "LIMITED"}
SERVING_STATUS = {2: "ELIGIBLE", 3: "RARELY_SERVED"}
IS_SENTINEL = 0.0999  # Google's value for "under 10%" impression share

CHANNELS = ["Shopping Ads", "Google Search", "Discover", "Gmail", "Google Display Network", "YouTube"]
OTHER_CH = "Cross-network & other"
TABLE_CHANNELS = CHANNELS + ["Maps", OTHER_CH]
CH_COLOR = {"Shopping Ads": "4285F4", "Google Search": "EA4335", "Discover": "FBBC04", "Gmail": "34A853",
            "Google Display Network": "A142F4", "YouTube": "FF6D01"}
FILTERS = ["PMax + Shopping", "PMax only", "Whole Account"]
CAMPAIGN_CAP = 15
CAMPAIGN_COLORS = ["34A853", "A142F4", "FF6D01", "46BDC6", "7BAAF7", "F07B72", "FCD04F", "71C287", "B39DDB",
                   "FF994D", "1A73E8", "D93025", "F9AB00", "188038", "9334E6", "E8710A"]
BUCKETS = ["Profitable", "Costly", "Low spend", "Zombies"]
BUCKET_FILL = {"Profitable": "B6D7A8", "Costly": "E06666", "Low spend": "F6B26B", "Zombies": "CCCCCC"}
BUCKET_CHART = {"Profitable": "6AA84F", "Costly": "CC0000", "Low spend": "F6B26B", "Zombies": "999999"}
ASSET_TYPES = ["Headlines", "Long Headlines", "Descriptions", "Images", "YouTube Video"]
SORT_METRICS = ["Cost", "Conversions", "Conv. value", "ROAS", "Clicks", "Impressions", "CTR", "Conv. rate"]
VIEWS = ["Last year", "This year (YTD)", "Last year + this year"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€", "AUD": "A$", "NZD": "NZ$", "CAD": "C$", "JPY": "¥", "INR": "₹",
           "SGD": "S$", "HKD": "HK$", "ZAR": "R", "CHF": "CHF ", "SEK": "kr ", "NOK": "kr ", "DKK": "kr "}

DATASETS = OrderedDict([
    ("account_monthly", "Account tab"),
    ("account_total_last_year", "Account tab totals"),
    ("account_total_this_year", "Account tab totals"),
    ("account_total_both", "Account tab totals"),
    ("account_network_monthly", "Search Volume tab (eligible impressions)"),
    ("campaigns_daily", "Channel Split and Campaign tabs (required)"),
    ("pmax_shopping_daily", "the Shopping Ads share of Performance Max"),
    ("assets", "Assets tab"),
    ("products", "Products tabs"),
    ("product_inventory", "Products tabs"),
    ("pmax_search_terms", "Keyword Gap tab"),
    ("search_keywords", "Keyword Gap tab"),
])


def fail(msg):
    sys.stderr.write("ERROR: %s\n" % msg)
    sys.exit(1)


def out(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def enum(v, table):
    if v is None:
        return ""
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        return table.get(int(v), str(v))
    return str(v)


def camel_to_snake(s):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", s).lower()


# ---------------------------------------------------------------------------------------------
# Loading: every source ends as {dataset: [flat rows keyed "resource.field"]}
# ---------------------------------------------------------------------------------------------
def flatten(obj, prefix="", outd=None):
    outd = {} if outd is None else outd
    for k, v in obj.items():
        key = ".".join(camel_to_snake(p) for p in str(k).split("."))
        path = prefix + "." + key if prefix else key
        if isinstance(v, dict):
            flatten(v, path, outd)
        else:
            outd[path] = v
    return outd


def rows_from(obj):
    """Find the rows in whatever shape a connection returned."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except ValueError:
            return None
    if isinstance(obj, list):
        if not obj:
            return []
        if all(isinstance(r, dict) for r in obj):
            if len(obj) == 1 and not any(k in obj[0] for k in ("campaign", "metrics", "segments")) and rows_from(obj[0]):
                return rows_from(obj[0])
            return [flatten(r) for r in obj]
        return None
    if isinstance(obj, dict):
        if "fields" in obj and "rows" in obj and isinstance(obj["rows"], list):
            fields = obj["fields"]
            return [{f: (r[i] if i < len(r) else None) for i, f in enumerate(fields)} for r in obj["rows"]]
        for key in ("results", "rows", "data", "result", "content", "text"):
            if key in obj:
                got = rows_from(obj[key])
                if got is not None:
                    return got
        if any(k in obj for k in ("campaign", "metrics", "segments", "customer")):
            return [flatten(obj)]
    return None


def read_text(path):
    raw = open(path, "rb").read()
    if path.endswith(".gz"):
        raw = gzip.decompress(raw)
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def read_table(text):
    lines = [l for l in text.splitlines() if l.strip()]
    first = lines[0] if lines else ""
    delim = max(["\t", ",", ";"], key=first.count)
    return list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))


def rows_from_file(path):
    text = read_text(path)
    stripped = text.lstrip()
    if stripped[:1] in "[{":
        try:
            data = json.loads(stripped)
        except ValueError as e:
            fail("%s is not valid JSON (%s). Save the query result again, complete." % (path, e))
        return data
    table = read_table(text)
    if not table:
        return []
    header = [h.strip() for h in table[0]]
    return [{header[i]: (r[i] if i < len(r) else "") for i in range(len(header))} for r in table[1:]]


def dataset_name(filename):
    stem = os.path.basename(filename)
    for ext in (".gz", ".json", ".csv", ".tsv", ".txt"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
    stem = stem.lower().replace("-", "_")
    for name in DATASETS:
        if stem == name or stem.endswith("_" + name):
            return name
    if stem in ("account_info", "account") or stem.endswith("_account_info"):
        return "account_info"
    return None


def cmd_load(a):
    src = a.source
    meta, datasets, errors = {}, {}, {}
    if os.path.isdir(src):
        for fn in sorted(os.listdir(src)):
            name = dataset_name(fn)
            if not name:
                continue
            rows = rows_from(rows_from_file(os.path.join(src, fn)))
            if rows is None:
                fail("Couldn't find rows in %s. Save the query result as JSON (the rows list) or CSV with field-path headers." % fn)
            datasets.setdefault(name, []).extend(rows)
    elif os.path.isfile(src):
        data = rows_from_file(src)
        if not isinstance(data, dict) or "datasets" not in data:
            fail("%s isn't the file the Google Ads Script saves. Pass that file, or a folder of query results." % src)
        meta = dict(data.get("meta") or {})
        errors = dict(data.get("errors") or {})
        for name, obj in (data.get("datasets") or {}).items():
            rows = rows_from(obj)
            datasets[name] = rows or []
    else:
        fail("No such file or folder: %s" % src)

    info = datasets.pop("account_info", None)
    if info:
        r = info[0]
        meta.setdefault("account_name", r.get("customer.descriptive_name"))
        meta.setdefault("currency_code", r.get("customer.currency_code"))
        meta.setdefault("customer_id", str(r.get("customer.id") or ""))
    for k, v in (("account_name", a.account_name), ("customer_id", a.customer_id), ("currency_code", a.currency),
                 ("date_from", a.date_from), ("date_to", a.date_to)):
        if v:
            meta[k] = v
    for k in ("date_from", "date_to"):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(meta.get(k) or "")):
            fail("The report's date range is unknown. Pass --from YYYY-MM-DD --to YYYY-MM-DD (the dates the queries used).")
    if not meta.get("calendar_from"):
        meta["calendar_from"] = "%d-01-01" % (int(meta["date_to"][:4]) - 1)
        meta["calendar_to"] = meta["date_to"]
    if not meta.get("currency_code"):
        fail("The account currency is unknown. Pass --currency (e.g. GBP), or save the account_info query.")
    meta["customer_id"] = re.sub(r"[^0-9]", "", str(meta.get("customer_id") or ""))
    if "campaigns_daily" not in datasets:
        fail("campaigns_daily is missing: it is the one query every tab needs. Run it and load again.")

    os.makedirs(a.run, exist_ok=True)
    target = os.path.join(a.run, "data.json")
    if os.path.exists(target) and not a.force:
        fail("%s already exists. Pass --force to replace it." % target)
    with open(target, "w", encoding="utf-8") as f:
        json.dump({"format": "google-ads-audit-analysis/1", "meta": meta, "datasets": datasets, "errors": errors}, f)
    missing = [n for n in DATASETS if n not in datasets]
    empty = [n for n in DATASETS if n in datasets and not datasets[n]]
    out({"saved": target, "account": meta.get("account_name"), "customer_id": meta.get("customer_id"),
         "currency": meta.get("currency_code"), "report_range": "%s to %s" % (meta["date_from"], meta["date_to"]),
         "rows": {n: len(datasets.get(n, [])) for n in DATASETS if n in datasets},
         "missing": {n: DATASETS[n] for n in missing}, "empty": {n: DATASETS[n] for n in empty},
         "export_errors": errors})


def load_run(run):
    p = os.path.join(run, "data.json")
    if not os.path.exists(p):
        fail("No %s yet. Run the load command first." % p)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------------------------
# Channel maths (Performance Max by network, the Shopping share from shopping_performance_view)
# ---------------------------------------------------------------------------------------------
def blank():
    return {"cost": 0.0, "conv": 0.0, "val": 0.0}


def add_metrics(t, r):
    t["cost"] += num(r.get("metrics.cost_micros")) / 1e6
    t["conv"] += num(r.get("metrics.conversions"))
    t["val"] += num(r.get("metrics.conversions_value"))


def add_raw(t, x):
    t["cost"] += x["cost"]
    t["conv"] += x["conv"]
    t["val"] += x["val"]


def split_channels(net, shop, shop_mixed):
    """Same rules as the Big Flare internal report. net: network -> metrics for one campaign (or campaign-day)."""
    def n(t):
        return net.get(t) or blank()
    srch, sp, mixed = n("SEARCH"), n("SEARCH_PARTNERS"), n("MIXED")
    unmapped = blank()
    for t, x in net.items():
        if t not in KNOWN_NETWORKS:
            add_raw(unmapped, x)
    yt = blank()
    for t in ("YOUTUBE", "YOUTUBE_SEARCH", "YOUTUBE_WATCH"):
        add_raw(yt, n(t))
    return {
        "Shopping Ads": {k: shop[k] + shop_mixed[k] for k in shop},
        "Google Search": {k: max(0.0, srch[k] - shop[k]) + sp[k] for k in shop},
        "Discover": n("DISCOVER"),
        "Gmail": n("GMAIL"),
        "Google Display Network": n("CONTENT"),
        "YouTube": yt,
        "Maps": n("MAPS"),
        OTHER_CH: {k: max(0.0, mixed[k] - shop_mixed[k]) + unmapped[k] for k in shop},
    }


def only_shopping(total):
    ch = {k: blank() for k in TABLE_CHANNELS}
    ch["Shopping Ads"] = dict(total)
    return ch


def aggregate_campaigns(ds):
    camp_rows = ds.get("campaigns_daily") or []
    shop_rows = ds.get("pmax_shopping_daily") or []
    camps = OrderedDict()
    for r in camp_rows:
        cid = str(r.get("campaign.id") or r.get("campaign.name"))
        c = camps.get(cid)
        if not c:
            c = camps[cid] = {"id": cid, "name": str(r.get("campaign.name") or cid),
                              "type": enum(r.get("campaign.advertising_channel_type"), CHANNEL_TYPE),
                              "net": defaultdict(blank), "days": defaultdict(lambda: defaultdict(blank))}
        nt = enum(r.get("segments.ad_network_type"), NETWORK)
        add_metrics(c["net"][nt], r)
        d = str(r.get("segments.date") or "")[:10]
        if d:
            add_metrics(c["days"][d][nt], r)
    shop = defaultdict(lambda: {"SEARCH": blank(), "MIXED": blank()})
    shop_day = defaultdict(lambda: {"SEARCH": blank(), "MIXED": blank()})
    for r in shop_rows:
        nt = enum(r.get("segments.ad_network_type"), NETWORK)
        if nt not in ("SEARCH", "MIXED"):
            continue
        cid = str(r.get("campaign.id"))
        add_metrics(shop[cid][nt], r)
        d = str(r.get("segments.date") or "")[:10]
        if d:
            add_metrics(shop_day[(cid, d)][nt], r)
    out_camps = []
    unknown = set()
    for c in camps.values():
        for t, x in c["net"].items():
            if t not in KNOWN_NETWORKS and x["cost"] > 0:
                unknown.add(t)
        if c["type"] == "PERFORMANCE_MAX":
            ch = split_channels(c["net"], shop[c["id"]]["SEARCH"], shop[c["id"]]["MIXED"])
            days = {d: split_channels(net, shop_day[(c["id"], d)]["SEARCH"], shop_day[(c["id"], d)]["MIXED"])
                    for d, net in c["days"].items()}
        else:
            tot = blank()
            for x in c["net"].values():
                add_raw(tot, x)
            if c["type"] == "SHOPPING":
                ch = only_shopping(tot)
                days = {}
                for d, net in c["days"].items():
                    t2 = blank()
                    for x in net.values():
                        add_raw(t2, x)
                    days[d] = only_shopping(t2)
            else:
                ch = split_channels(c["net"], blank(), blank())
                days = {d: split_channels(net, blank(), blank()) for d, net in c["days"].items()}
        total = blank()
        for x in ch.values():
            add_raw(total, x)
        if total["cost"] <= 0 and total["conv"] <= 0:
            continue
        out_camps.append({"id": c["id"], "name": c["name"], "type": c["type"], "ch": ch, "days": days, "total": total})
    out_camps.sort(key=lambda c: (-c["total"]["cost"], c["name"]))
    names = defaultdict(int)
    for c in out_camps:
        names[c["name"]] += 1
    for c in out_camps:
        if names[c["name"]] > 1:
            c["name"] = "%s (%s)" % (c["name"], c["id"])
    return out_camps, sorted(unknown)


def in_filter(c, f):
    if f == "PMax only":
        return c["type"] == "PERFORMANCE_MAX"
    if f == "PMax + Shopping":
        return c["type"] in ("PERFORMANCE_MAX", "SHOPPING")
    return True


def cap_campaigns(camps):
    if len(camps) <= CAMPAIGN_CAP + 1:
        return camps
    rest = camps[CAMPAIGN_CAP:]
    ch = {k: blank() for k in TABLE_CHANNELS}
    total = blank()
    for c in rest:
        for k in TABLE_CHANNELS:
            add_raw(ch[k], c["ch"][k])
        add_raw(total, c["total"])
    return camps[:CAMPAIGN_CAP] + [{"id": "other", "name": "Other campaigns (%d)" % len(rest), "type": "", "ch": ch,
                                    "total": total, "days": {}}]


# ---------------------------------------------------------------------------------------------
# Assets, products, families, keyword gaps
# ---------------------------------------------------------------------------------------------
def asset_field(r):
    raw = r.get("asset_group_asset.field_type")
    if isinstance(raw, str) and raw and not raw.isdigit():
        return raw
    rn = str(r.get("asset_group_asset.resource_name") or "")
    if "~" in rn:
        return rn.split("~")[-1]
    return enum(raw, ASSET_FIELD)


def asset_type(field):
    return {"HEADLINE": "Headlines", "LONG_HEADLINE": "Long Headlines", "DESCRIPTION": "Descriptions",
            "YOUTUBE_VIDEO": "YouTube Video"}.get(field) or ("Images" if field in IMAGE_FIELDS else None)


def aggregate_assets(rows):
    by = OrderedDict()
    for r in rows:
        field = asset_field(r)
        typ = asset_type(field)
        if not typ:
            continue
        src = enum(r.get("asset_group_asset.source"), ASSET_SOURCE)
        src = {"ADVERTISER": "Advertiser", "AUTOMATICALLY_CREATED": "Automatically created"}.get(src, src.replace("_", " ").title() if src else "Unknown")
        aid = str(r.get("asset.id") or "")
        key = (typ, aid, src)
        x = by.get(key)
        if not x:
            yt = r.get("asset.youtube_video_asset.youtube_video_id")
            name = (r.get("asset.text_asset.text") or r.get("asset.youtube_video_asset.youtube_video_title")
                    or ("YouTube video %s" % yt if yt else "") or r.get("asset.name") or "Asset %s" % aid)
            link = ("https://www.youtube.com/watch?v=%s" % yt) if yt else (r.get("asset.image_asset.full_size.url") or "")
            x = by[key] = {"type": typ, "id": aid, "source": src, "name": str(name), "link": link, "fields": set(),
                           "impr": 0.0, "clicks": 0.0, "cost": 0.0, "conv": 0.0, "val": 0.0}
        x["fields"].add(field.replace("_", " ").title())
        x["impr"] += num(r.get("metrics.impressions"))
        x["clicks"] += num(r.get("metrics.clicks"))
        x["cost"] += num(r.get("metrics.cost_micros")) / 1e6
        x["conv"] += num(r.get("metrics.conversions"))
        x["val"] += num(r.get("metrics.conversions_value"))
    items = list(by.values())
    for x in items:
        x["fields"] = ", ".join(sorted(x["fields"]))
    items.sort(key=lambda x: (-x["impr"], x["name"]))
    return items


def pkey(s):
    return str(s or "").strip().lower()


def aggregate_products(perf_rows, inv_rows):
    inv = OrderedDict()
    for r in inv_rows:
        pid = str(r.get("shopping_product.item_id") or "").strip()
        if not pid:
            continue
        x = inv.setdefault(pkey(pid), {"id": pid, "title": "", "feeds": set(), "statuses": set(), "brand": "",
                                       "ptype": ""})
        if r.get("shopping_product.title") and not x["title"]:
            x["title"] = str(r.get("shopping_product.title"))
        if r.get("shopping_product.feed_label"):
            x["feeds"].add(str(r.get("shopping_product.feed_label")))
        st = r.get("shopping_product.status")
        if st not in (None, ""):
            st = enum(st, PRODUCT_STATUS)
            x["statuses"].add(PRODUCT_STATUS.get({"UNKNOWN": 1, "NOT_ELIGIBLE": 2, "ELIGIBLE_LIMITED": 3, "ELIGIBLE": 4}.get(st, 0), st))
        x["brand"] = x["brand"] or str(r.get("shopping_product.brand") or "")
        x["ptype"] = x["ptype"] or " > ".join(str(r.get(k)) for k in ("shopping_product.product_type_level1",
                                                                     "shopping_product.product_type_level2") if r.get(k))
    stats = defaultdict(lambda: {"impr": 0.0, "clicks": 0.0, "cost": 0.0, "conv": 0.0, "val": 0.0, "titles": defaultdict(float)})
    no_inventory = not inv
    for r in perf_rows:
        ctype = enum(r.get("campaign.advertising_channel_type"), CHANNEL_TYPE)
        nt = enum(r.get("segments.ad_network_type"), NETWORK)
        if ctype == "PERFORMANCE_MAX" and nt != "SEARCH":
            continue
        if ctype not in ("PERFORMANCE_MAX", "SHOPPING"):
            continue
        pid = str(r.get("segments.product_item_id") or "").strip()
        k = pkey(pid)
        if not k:
            continue
        if k not in inv:
            if not no_inventory:
                continue  # retired IDs: the report covers the products listed today
            inv[k] = {"id": pid, "title": "", "feeds": set(), "statuses": set(), "brand": "", "ptype": ""}
        s = stats[k]
        s["impr"] += num(r.get("metrics.impressions"))
        s["clicks"] += num(r.get("metrics.clicks"))
        cost = num(r.get("metrics.cost_micros")) / 1e6
        s["cost"] += cost
        s["conv"] += num(r.get("metrics.conversions"))
        s["val"] += num(r.get("metrics.conversions_value"))
        if r.get("segments.product_title"):
            s["titles"][str(r.get("segments.product_title"))] += cost
        if r.get("segments.product_feed_label"):
            inv[k]["feeds"].add(str(r.get("segments.product_feed_label")))
    items = []
    for k, x in inv.items():
        s = stats.get(k) or {"impr": 0.0, "clicks": 0.0, "cost": 0.0, "conv": 0.0, "val": 0.0, "titles": {}}
        title = x["title"] or (max(s["titles"].items(), key=lambda t: t[1])[0] if s["titles"] else "") or "[Untitled product %s]" % x["id"]
        items.append({"id": x["id"], "title": title, "feeds": ", ".join(sorted(x["feeds"])),
                      "statuses": ", ".join(sorted(x["statuses"])), "brand": x["brand"], "ptype": x["ptype"],
                      "impr": s["impr"], "clicks": s["clicks"], "cost": s["cost"], "conv": s["conv"], "val": s["val"]})
    items.sort(key=lambda x: (-x["cost"], x["id"]))
    return items, no_inventory


def bucket(cost, roas, cost_t, roas_t):
    if cost == 0:
        return "Zombies"
    if cost < cost_t:
        return "Low spend"
    return "Profitable" if roas >= roas_t else "Costly"


SHOPIFY_ID = re.compile(r"^shopify_[a-z]{2}_(\d+)_(\d+)", re.I)
SIZE_TOKEN = re.compile(r"\b\d+(\.\d+)?\s?(ml|l|g|kg|oz|lb|lbs|cm|mm|m|in|inch|pack|pk|pcs|x)\b", re.I)


def family_name_from_titles(titles):
    titles = [t for t in titles if t]
    if not titles:
        return ""
    heads = [re.split(r"\s+[|–—]\s+|\s+-\s+", t)[0].strip() for t in titles]
    words = [h.split() for h in heads]
    common = []
    for parts in zip(*words):
        if all(p.lower() == parts[0].lower() for p in parts):
            common.append(parts[0])
        else:
            break
    name = " ".join(common).strip(" ,-|") if len(common) >= 2 else min(heads, key=len)
    return SIZE_TOKEN.sub("", name).strip(" ,-|") or name


def suggest_families(products):
    groups = OrderedDict()
    rule_counts = defaultdict(int)
    for p in products:
        m = SHOPIFY_ID.match(p["id"])
        if m:
            key, rule = "shopify:" + m.group(1), "Shopify product ID"
        else:
            head = re.split(r"\s+[|–—]\s+|\s+-\s+|,\s+", p["title"])[0]
            head = SIZE_TOKEN.sub("", head)
            head = re.sub(r"\s*[\(\[].*?[\)\]]", "", head)
            key, rule = "title:" + re.sub(r"\s+", " ", head).strip().lower(), "Title"
        groups.setdefault(key, {"rule": rule, "items": []})["items"].append(p)
    # Groups that end up with the same name are the same product listed twice (a title test, a re-upload):
    # they share one family.
    named = OrderedDict()
    for key, g in groups.items():
        name = family_name_from_titles([p["title"] for p in g["items"]]) or g["items"][0]["title"]
        named.setdefault(name.lower(), {"name": name, "rules": set(), "items": []})
        named[name.lower()]["rules"].add(g["rule"])
        named[name.lower()]["items"].extend(g["items"])
    rows = []
    for g in named.values():
        rule_counts[" + ".join(sorted(g["rules"]))] += 1
        for p in g["items"]:
            rows.append({"product_id": p["id"], "family": g["name"], "title": p["title"]})
    return rows, dict(rule_counts)


def read_families(run, products):
    path = os.path.join(run, "product-families.csv")
    if not os.path.exists(path):
        return None
    mapping = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pid = (r.get("product_id") or "").strip()
            fam = (r.get("family") or "").strip()
            if pid and fam:
                mapping[pkey(pid)] = fam
    return mapping


def cmd_families(a):
    data = load_run(a.run)
    products, _ = aggregate_products(data["datasets"].get("products") or [], data["datasets"].get("product_inventory") or [])
    if not products:
        fail("No products in this account's data, so there are no families to suggest.")
    rows, rules = suggest_families(products)
    path = os.path.join(a.run, "product-families.csv")
    if os.path.exists(path) and not a.write:
        fail("%s already exists (maybe edited). Pass --write to replace it with a fresh suggestion." % path)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["product_id", "family", "title"])
        w.writeheader()
        w.writerows(rows)
    fam = defaultdict(list)
    cost = {pkey(p["id"]): p["cost"] for p in products}
    for r in rows:
        fam[r["family"]].append(r)
    biggest = sorted(fam.items(), key=lambda kv: -sum(cost[pkey(x["product_id"])] for x in kv[1]))[:15]
    out({"saved": path, "products": len(products), "families": len(fam),
         "single_product_families": sum(1 for v in fam.values() if len(v) == 1),
         "grouped_by": rules,
         "top_families_by_cost": [{"family": k, "products": len(v), "cost": round(sum(cost[pkey(x["product_id"])] for x in v), 2),
                                   "sample_titles": [x["title"] for x in v[:3]]} for k, v in biggest],
         "next": "Check the families read as real products. Edit the family column in the CSV to merge or split, then build."})


def norm_kw(s):
    return re.sub(r"\s+", " ", re.sub(r"\+", "", re.sub(r"[\[\]\"]+", "", str(s or "")))).strip().lower()


def title_status(s):
    return str(s or "").replace("_", " ").lower().capitalize()


def kw_status(r):
    crit = enum(r.get("ad_group_criterion.status"), ENTITY_STATUS)
    if crit and crit != "ENABLED":
        return "Keyword " + title_status(crit).lower()
    reasons = r.get("ad_group_criterion.primary_status_reasons") or []
    if isinstance(reasons, str):
        reasons = [x for x in re.split(r"[,;|]\s*", reasons.strip("[]")) if x]
    if reasons:
        return ", ".join(title_status(str(x).strip("'\" ")) for x in reasons)
    primary = enum(r.get("ad_group_criterion.primary_status"), PRIMARY_STATUS)
    if primary and primary != "ELIGIBLE":
        return title_status(primary)
    serving = enum(r.get("ad_group_criterion.system_serving_status"), SERVING_STATUS)
    if serving and serving != "ELIGIBLE":
        return title_status(serving)
    ag = enum(r.get("ad_group.status"), ENTITY_STATUS)
    if ag and ag != "ENABLED":
        return "Ad group " + title_status(ag).lower()
    cs = enum(r.get("campaign.status"), ENTITY_STATUS)
    if cs and cs != "ENABLED":
        return "Campaign " + title_status(cs).lower()
    return "Not eligible"


def kw_eligible(r):
    crit = enum(r.get("ad_group_criterion.status"), ENTITY_STATUS)
    primary = enum(r.get("ad_group_criterion.primary_status"), PRIMARY_STATUS)
    serving = enum(r.get("ad_group_criterion.system_serving_status"), SERVING_STATUS)
    ag = enum(r.get("ad_group.status"), ENTITY_STATUS)
    cs = enum(r.get("campaign.status"), ENTITY_STATUS)
    return crit == "ENABLED" and ag == "ENABLED" and cs == "ENABLED" and (primary == "ELIGIBLE" or (not primary and serving == "ELIGIBLE"))


def keyword_gaps(term_rows, kw_rows):
    terms = OrderedDict()
    for r in term_rows:
        text = str(r.get("campaign_search_term_view.search_term") or "").strip()
        k = norm_kw(text)
        if not k:
            continue
        x = terms.setdefault(k, {"term": text, "clicks": 0.0, "impr": 0.0, "conv": 0.0, "cost": 0.0, "val": 0.0})
        x["clicks"] += num(r.get("metrics.clicks"))
        x["impr"] += num(r.get("metrics.impressions"))
        x["conv"] += num(r.get("metrics.conversions"))
        x["cost"] += num(r.get("metrics.cost_micros")) / 1e6
        x["val"] += num(r.get("metrics.conversions_value"))
    kws = defaultdict(list)
    for r in kw_rows:
        k = norm_kw(r.get("ad_group_criterion.keyword.text"))
        if k:
            kws[k].append(r)
    gaps = []
    for k, x in terms.items():
        if x["conv"] <= 0:
            continue
        matches = kws.get(k, [])
        if any(kw_eligible(m) for m in matches):
            continue
        missing = not matches
        status = "No keyword" if missing else "; ".join(sorted({kw_status(m) for m in matches}))
        gaps.append(dict(x, issue="Missing keyword" if missing else "Not eligible", status=status,
                         action="Add as a keyword" if missing else "Fix or unpause the keyword"))
    gaps.sort(key=lambda g: (-g["conv"], -g["cost"], g["term"]))
    return gaps


# ---------------------------------------------------------------------------------------------
# Account months and Search Volume
# ---------------------------------------------------------------------------------------------
def month_key(v):
    s = str(v or "")
    return s[:7] if re.match(r"^\d{4}-\d{2}", s) else ""


def month_label(ym):
    return "%s %s" % (MONTHS[int(ym[5:7]) - 1], ym[:4])


def shift_month(ym, n):
    y, m = int(ym[:4]), int(ym[5:7])
    i = y * 12 + m - 1 + n
    return "%04d-%02d" % (i // 12, i % 12 + 1)


def month_range(a, b):
    outl = []
    m = a
    while m <= b:
        outl.append(m)
        m = shift_month(m, 1)
    return outl


def account_metrics(rows):
    t = {"conv": 0.0, "cost": 0.0, "val": 0.0, "val_ct": 0.0, "is": None, "rank": None, "budget": None}
    for r in rows:
        t["conv"] += num(r.get("metrics.conversions"))
        t["cost"] += num(r.get("metrics.cost_micros")) / 1e6
        t["val"] += num(r.get("metrics.conversions_value"))
        t["val_ct"] += num(r.get("metrics.conversions_value_by_conversion_date"))
        if len(rows) == 1:
            for k, f in (("is", "metrics.search_impression_share"), ("rank", "metrics.search_rank_lost_impression_share"),
                         ("budget", "metrics.search_budget_lost_impression_share")):
                v = r.get(f)
                t[k] = None if v in (None, "") else num(v)
    return t


def account_model(ds, meta):
    rows = ds.get("account_monthly") or []
    if not rows:
        return None
    cal_from, cal_to = meta["calendar_from"][:7], meta["calendar_to"][:7]
    months = month_range(cal_from, cal_to)
    by = defaultdict(list)
    for r in rows:
        by[month_key(r.get("segments.month"))].append(r)
    monthly = [(m, account_metrics(by.get(m, []))) for m in months]
    year = int(meta["calendar_to"][:4])
    totals = {}
    for view, key, filt in (("Last year", "account_total_last_year", lambda m: m.startswith(str(year - 1))),
                            ("This year (YTD)", "account_total_this_year", lambda m: m.startswith(str(year))),
                            ("Last year + this year", "account_total_both", lambda m: True)):
        src = ds.get(key)
        if src:
            totals[view] = account_metrics(src[:1])
        else:
            t = account_metrics([])
            for m, x in monthly:
                if filt(m):
                    for k in ("conv", "cost", "val", "val_ct"):
                        t[k] += x[k]
            totals[view] = t
    net = defaultdict(lambda: {"search": 0.0, "mixed": 0.0})
    for r in ds.get("account_network_monthly") or []:
        nt = enum(r.get("segments.ad_network_type"), NETWORK)
        m = month_key(r.get("segments.month"))
        if nt == "SEARCH":
            net[m]["search"] += num(r.get("metrics.impressions"))
        elif nt == "MIXED":
            net[m]["mixed"] += num(r.get("metrics.impressions"))
    return {"months": monthly, "totals": totals, "year": year, "network": dict(net),
            "ly_count": sum(1 for m, _ in monthly if m.startswith(str(year - 1))),
            "ty_count": sum(1 for m, _ in monthly if m.startswith(str(year))), "has_network": bool(ds.get("account_network_monthly"))}


PLANNER_MONTH = re.compile(r"^searches:\s*([A-Za-z]{3})[a-z]*\s+(\d{4})$", re.I)


def cmd_planner(a):
    text = read_text(a.file)
    keywords = []
    stripped = text.lstrip()
    if stripped[:1] in "[{":
        data = json.loads(stripped)
        rows = rows_from(data) or []
        for r in rows:
            kw = r.get("text") or r.get("keyword") or r.get("search_query") or ""
            vols = None
            for k, v in r.items():
                if k.endswith("monthly_search_volumes") and isinstance(v, list):
                    vols = v
            if not kw or vols is None:
                continue
            monthly = {}
            for v in vols:
                v = flatten(v) if isinstance(v, dict) else {}
                y = v.get("year")
                mo = v.get("month")
                if isinstance(mo, str) and not mo.isdigit():
                    mo = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
                          "OCTOBER", "NOVEMBER", "DECEMBER"].index(mo.upper()) + 1
                else:
                    mo = int(num(mo))
                    if mo > 12:
                        mo -= 1  # the API's month enum: 2 = January
                if y and mo:
                    monthly["%04d-%02d" % (int(num(y)), mo)] = num(v.get("monthly_searches"))
            keywords.append({"text": str(kw), "monthly": monthly})
    else:
        table = read_table(text)
        start = 0
        for i, row in enumerate(table[:12]):
            if any(c.strip().lower() == "keyword" for c in row):
                start = i
                break
        header = [h.strip() for h in table[start]]
        kcol = [h.lower() for h in header].index("keyword")
        mcols = []
        for i, h in enumerate(header):
            m = PLANNER_MONTH.match(h)
            if m:
                mcols.append((i, "%s-%02d" % (m.group(2), [x.lower() for x in MONTHS].index(m.group(1).lower()[:3]) + 1)))
        if not mcols:
            fail("No 'Searches: Mon YYYY' columns in %s. In Keyword Planner use 'Get search volume and forecasts', "
                 "open Historical metrics, set the date range, and download that table." % a.file)
        for row in table[start + 1:]:
            if kcol >= len(row) or not row[kcol].strip():
                continue
            monthly = {}
            for i, ym in mcols:
                if i < len(row) and row[i].strip() not in ("", "--"):
                    monthly[ym] = num(row[i].replace(" ", ""))
            keywords.append({"text": row[kcol].strip(), "monthly": monthly})
    if not keywords:
        fail("No keywords with monthly searches found in %s." % a.file)
    path = os.path.join(a.run, "search-volume.json")
    os.makedirs(a.run, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"market": a.market or "", "language": a.language or "", "keywords": keywords}, f, indent=1)
    months = sorted({m for k in keywords for m in k["monthly"]})
    out({"saved": path, "keywords": len(keywords), "months": "%s to %s" % (months[0], months[-1]) if months else "none",
         "market": a.market, "keywords_list": [k["text"] for k in keywords]})


def search_volume_model(sv, acct, meta):
    if not sv or not sv.get("keywords"):
        return None
    months = month_range(meta["calendar_from"][:7], meta["calendar_to"][:7])
    to = meta["calendar_to"]
    last_day = (dt.date(int(to[:4]) + (1 if to[5:7] == "12" else 0), 1 if to[5:7] == "12" else int(to[5:7]) + 1, 1)
                - dt.timedelta(days=1)).day
    complete = to[:7] if int(to[8:10]) == last_day else shift_month(to[:7], -1)
    have = sorted({m for k in sv["keywords"] for m in k["monthly"]})
    if have:
        complete = min(complete, have[-1])
    kws = [k["text"] for k in sv["keywords"]]
    vals = {(k["text"], m): v for k in sv["keywords"] for m, v in k["monthly"].items()}

    def kw(k, m):
        return None if m > complete else vals.get((k, m))

    def total(m):
        xs = [kw(k, m) for k in kws]
        return None if not xs or any(x is None for x in xs) else sum(xs)
    acct_month = dict(acct["months"]) if acct else {}
    net = acct["network"] if acct else {}

    def eligible(m):
        x = acct_month.get(m)
        n = net.get(m)
        if m > complete or not x or not n or n["mixed"] > 0 or not x["is"] or abs(x["is"] - IS_SENTINEL) < 1e-9:
            return None
        return n["search"] / x["is"]
    year = int(to[:4])
    avail = [m for m in months if m.startswith(str(year)) and total(m) is not None]
    latest = avail[-1] if avail else None
    ytd = month_range("%d-01" % year, latest) if latest else []
    recent = month_range(shift_month(latest, -2), latest) if latest else []

    def avg(fn, ms):
        xs = [fn(m) for m in ms]
        return None if not xs or any(x is None for x in xs) else sum(xs) / len(xs)

    def span(ms):
        return "%s – %s" % (month_label(ms[0]), month_label(ms[-1])) if ms else "no complete months"
    comps = []
    for name, cur in (("Year to date", ytd), ("Latest 3 months", recent)):
        prior = [shift_month(m, -12) for m in cur]
        rows = []
        for label, fn in (("Avg monthly searches", total), ("Avg eligible impressions", eligible)):
            a_, b_ = avg(fn, cur), avg(fn, prior)
            rows.append((label, b_, a_, (a_ / b_ - 1) if a_ is not None and b_ else None))
        comps.append({"name": name, "prior": span(prior), "current": span(cur), "rows": rows})
    return {"months": months, "keywords": kws, "kw": kw, "total": total, "eligible": eligible, "complete": complete,
            "comparisons": comps, "market": sv.get("market") or "", "language": sv.get("language") or "",
            "has_eligible": bool(acct and acct.get("has_network"))}


# ---------------------------------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------------------------------
NAVY, BLUE, PINK, CREAM, BAND, TOTAL = "1F3864", "2E75B6", "F4CCCC", "FFF2CC", "F3F6FA", "DDEBF7"
TABS = {"start": "DC2929", "account": "1F3864", "sv": "C27BA0", "channel": "CC0000", "campaign": "38761D",
        "assets": "3C78D8", "products": "674EA7", "families": "45818E", "mapping": "76A5AF", "gap": "F1C232"}


class Book:
    def __init__(self, store, meta, symbol):
        self.wb = Workbook()
        self.store = store
        self.meta = meta
        self.sym = symbol
        w = self.wb
        self.s = {
            "banner": w.style(bold=True, color="FFFFFF", fill=NAVY, size=14, indent=1),
            "sub": w.style(color="FFFFFF", fill=BLUE, size=9, indent=1),
            "chip": w.style(bold=True, fill=PINK, h="center"),
            "drop": w.style(bold=True, fill=CREAM, h="center", border={"left": "thin", "right": "thin", "top": "thin", "bottom": "thin", "color": "BF9000"}),
            "drop_pct": w.style(bold=True, fill=CREAM, h="center", fmt="0%", border={"left": "thin", "right": "thin", "top": "thin", "bottom": "thin", "color": "BF9000"}),
            "drop_money": w.style(bold=True, fill=CREAM, h="center", fmt=self.money(0), border={"left": "thin", "right": "thin", "top": "thin", "bottom": "thin", "color": "BF9000"}),
            "hint": w.style(italic=True, color="808080", size=9),
            "hdr": w.style(bold=True, color="FFFFFF", fill=NAVY, h="center", wrap=True),
            "hdr_l": w.style(bold=True, color="FFFFFF", fill=NAVY, wrap=True, indent=1),
            "hdr_teal": w.style(bold=True, color="FFFFFF", fill="0F766E", h="center", wrap=True),
            "text": w.style(),
            "text_l": w.style(indent=1),
            "wrap": w.style(wrap=True, v="top"),
            "bold": w.style(bold=True),
            "int": w.style(fmt="#,##0"),
            "dec": w.style(fmt="#,##0.00"),
            "money": w.style(fmt=self.money(2)),
            "money0": w.style(fmt=self.money(0)),
            "pct": w.style(fmt="0.0%"),
            "pct2": w.style(fmt="0.00%"),
            "pct0": w.style(fmt="0%"),
            "roas": w.style(fmt='0.00"x"'),
            "date": w.style(fmt="d mmm yyyy"),
            "date_short": w.style(fmt="d mmm"),
            "value_l": w.style(h="left"),
            "link": w.style(color="0F766E", underline=True),
            "h2": w.style(bold=True, size=12, color=NAVY),
            "label": w.style(bold=True, fill="F2F2F2", indent=1),
            "big": w.style(bold=True, size=12),
            "right_i": w.style(italic=True, color="808080", size=9, h="right"),
            "ghost": w.style(color="FFFFFF", size=6),
        }
        self.dx_total = w.dxf(bold=True, fill=TOTAL)
        self.dx_band = w.dxf(fill=BAND)
        self.dx_neg = w.dxf(bold=True, color="C00000")
        self.lists = None
        self.list_col = 0

    def money(self, dp):
        sym = self.sym.replace('"', "")
        return '"%s"#,##0%s' % (sym, ("." + "0" * dp) if dp else "")

    def banner(self, ws, title, subtitle, width_cols):
        ws.merge(0, 0, 0, width_cols - 1, title, self.s["banner"])
        ws.height(0, 30)
        ws.merge(1, 0, 1, width_cols - 1, subtitle + "   ·   Built with the Big Flare Skills Pack", self.s["sub"])
        ws.height(1, 18)

    def subtitle(self, extra=""):
        m = self.meta
        parts = [extra] if extra else []
        parts.append(self.domain)
        if m.get("customer_id"):
            c = m["customer_id"]
            parts.append("Account %s-%s-%s" % (c[:3], c[3:6], c[6:]) if len(c) == 10 else "Account %s" % c)
        return "   ·   ".join(p for p in parts if p)

    def add_list(self, values):
        """Put a dropdown's options on the hidden Lists tab and return the range."""
        if self.lists is None:
            self.lists = self.wb.sheet("Lists", hidden=True)
        c = self.list_col
        self.list_col += 1
        for i, v in enumerate(values):
            self.lists.set(i, c, Text(v))
        return "%s!$%s$1:$%s$%d" % (quote_sheet("Lists"), col_letter(c), col_letter(c), max(1, len(values)))


def fmt_range(meta):
    a = dt.date.fromisoformat(meta["date_from"])
    b = dt.date.fromisoformat(meta["date_to"])
    if a.year == b.year:
        return "%d %s – %d %s %d" % (a.day, MONTHS[a.month - 1], b.day, MONTHS[b.month - 1], b.year)
    return "%d %s %d – %d %s %d" % (a.day, MONTHS[a.month - 1], a.year, b.day, MONTHS[b.month - 1], b.year)


def safe_div(a, b):
    return a / b if b else 0.0


def trend_periods(meta):
    """Daily points for ranges up to 92 days, weekly (Monday-start) beyond. Returns (period starts, day->start, unit)."""
    d0 = dt.date.fromisoformat(meta["date_from"])
    d1 = dt.date.fromisoformat(meta["date_to"])
    days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
    if len(days) <= 92:
        return [d.isoformat() for d in days], (lambda iso: iso), "day"
    def start(iso):
        d = dt.date.fromisoformat(iso)
        return max(d0, d - dt.timedelta(days=d.weekday())).isoformat()
    starts = sorted({start(d.isoformat()) for d in days})
    return starts, start, "week"


def roll_days(days, mapper):
    """Sum a campaign's {day: {channel: metrics}} into {period: {channel: metrics}}."""
    outd = {}
    for d, ch in days.items():
        p = mapper(d)
        t = outd.setdefault(p, {k: blank() for k in TABLE_CHANNELS})
        for k in TABLE_CHANNELS:
            add_raw(t[k], ch[k])
    return outd


# ---- Account tab ------------------------------------------------------------------------------
def tab_account(bk, acct):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Account", tab=TABS["account"])
    data = wb.sheet("Account Data", hidden=True)
    q = data.q
    n = len(acct["months"])
    data.row(0, 0, ["Month", "Conversions", "Cost", "Conv. value", "Conv. value (by conv. time)", "Search impr. share",
                    "Lost IS (rank)", "Lost IS (budget)"])
    for i, (m, x) in enumerate(acct["months"]):
        r = i + 1
        data.set(r, 0, Text(month_label(m)))
        data.row(r, 1, [x["conv"], x["cost"], x["val"], x["val_ct"]])
        for j, k in enumerate(("is", "rank", "budget")):
            v = x[k]
            if k == "is" and v is not None and abs(v - IS_SENTINEL) < 1e-9:
                data.set(r, 5 + j, Text("< 10%"))
            elif v is not None and x["cost"] > 0:
                data.set(r, 5 + j, v)
    data.row(0, 10, ["View", "Conversions", "Cost", "Conv. value", "Conv. value (by conv. time)", "Search impr. share",
                     "Lost IS (rank)", "Lost IS (budget)"])
    for i, view in enumerate(VIEWS):
        t = acct["totals"][view]
        data.set(i + 1, 10, Text(view))
        data.row(i + 1, 11, [t["conv"], t["cost"], t["val"], t["val_ct"]])
        for j, k in enumerate(("is", "rank", "budget")):
            v = t[k]
            if k == "is" and v is not None and abs(v - IS_SENTINEL) < 1e-9:
                data.set(i + 1, 15 + j, Text("< 10%"))
            elif v is not None:
                data.set(i + 1, 15 + j, v)
    ly, ty = acct["ly_count"], acct["ty_count"]
    data.set(0, 19, "Start")
    data.set(1, 19, '=IF(Account!$B$4="This year (YTD)",%d,1)' % (ly + 1))
    data.set(2, 19, "Count")
    data.set(3, 19, '=IF(Account!$B$4="Last year",%d,IF(Account!$B$4="This year (YTD)",%d,%d))' % (ly, ty, ly + ty))

    y = acct["year"]
    bk.banner(ws, "%s — Account Overview by Month" % bk.store,
              bk.subtitle("All campaign types   ·   %s to %s" % (month_label(acct["months"][0][0]), month_label(acct["months"][-1][0]))), 12)
    ws.set(3, 0, "Choose a view:", s["chip"])
    ws.merge(3, 1, 3, 2, "Last year + this year", s["drop"])
    ws.dropdown(3, 1, VIEWS)
    ws.set(3, 3, "👈 last year, this year, or both", s["hint"])
    ws.set(3, 5, "Gross margin %:", s["chip"])
    ws.set(3, 6, bk.margin, s["drop_pct"])
    ws.set(3, 7, "👈 your average gross margin", s["hint"])
    ws.height(3, 24)
    ws.set(4, 0, "Gross profit after ad spend = Conv. value (by conv. time) × gross margin − Cost. Change the margin and every row "
           "recalculates. 'By conv. time' credits each sale to the day it happened, so recent months aren't understated.", s["hint"])
    heads = ["Month", "Conversions", "Cost / conv.", "Cost", "Conv. value", "ROAS", "Conv. value (by conv. time)",
             "ROAS (by conv. time)", "Search impr. share", "Search lost IS (rank)", "Search lost IS (budget)",
             "Gross profit after ad spend"]
    for c, h in enumerate(heads):
        ws.set(6, c, h, s["hdr_teal"] if c == 11 else s["hdr"])
    ws.height(6, 44)
    start = "%s!$T$2" % q
    count = "%s!$T$4" % q
    tot_match = "MATCH($B$4,%s!$K$2:$K$4,0)" % q
    src_cols = {1: "B", 3: "C", 4: "D", 6: "E", 8: "F", 9: "G", 10: "H"}
    tot_cols = {1: "L", 3: "M", 4: "N", 6: "O", 8: "P", 9: "Q", 10: "R"}
    styles = {1: s["int"], 2: s["money"], 3: s["money0"], 4: s["money0"], 5: s["roas"], 6: s["money0"], 7: s["roas"],
              8: s["pct2"], 9: s["pct2"], 10: s["pct2"], 11: s["money0"]}
    rows = n + 1
    for k in range(1, rows + 1):
        r = 6 + k
        rr = r + 1
        ws.set(r, 0, '=IF(%d<=%s,INDEX(%s!$A$2:$A$%d,%s+%d),IF(%d=%s+1,"Total",""))' % (k, count, q, n + 1, start, k - 1, k, count), s["bold"] if False else s["text_l"])
        for c, col in src_cols.items():
            ws.set(r, c, '=IF($A%d="","",IF($A%d="Total",INDEX(%s!$%s$2:$%s$4,%s),INDEX(%s!$%s$2:$%s$%d,%s+%d)))'
                   % (rr, rr, q, tot_cols[c], tot_cols[c], tot_match, q, col, col, n + 1, start, k - 1), styles[c])
        ws.set(r, 2, '=IF($A%d="","",IFERROR(D%d/B%d,0))' % (rr, rr, rr), styles[2])
        ws.set(r, 5, '=IF($A%d="","",IFERROR(E%d/D%d,0))' % (rr, rr, rr), styles[5])
        ws.set(r, 7, '=IF($A%d="","",IFERROR(G%d/D%d,0))' % (rr, rr, rr), styles[7])
        ws.set(r, 11, '=IF($A%d="","",G%d*$G$4-D%d)' % (rr, rr, rr), styles[11])
    last = 6 + rows
    ws.conditional(rng(7, 0, last, 11), '$A8="Total"', bk.dx_total)
    ws.conditional(rng(7, 0, last, 11), 'AND($A8<>"",ISEVEN(ROW()))', bk.dx_band)
    ws.conditional(rng(7, 11, last, 11), 'AND(ISNUMBER($L8),$L8<0)', bk.dx_neg)
    ws.width(0, 16)
    for c in range(1, 11):
        ws.width(c, 14)
    ws.width(11, 18)
    ws.freeze = (7, 1)
    return ws


# ---- Search Volume tab ------------------------------------------------------------------------
def tab_search_volume(bk, sv):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Search Volume", tab=TABS["sv"])
    kws = sv["keywords"]
    width = max(6, 3 + len(kws))
    scope = "Google Keyword Planner" + ("   ·   %s" % sv["market"] if sv["market"] else "") + \
        ("   ·   %s" % sv["language"] if sv["language"] else "") + "   ·   %d keywords" % len(kws)
    bk.banner(ws, "%s — Search Volume by Month" % bk.store, bk.subtitle(scope), min(width, 12))
    ws.set(3, 0, "Is the market growing or shrinking? Monthly Google searches for the keywords below, next to the impressions "
           "the account was eligible for. Months without a complete figure are blank: the current month, months Keyword Planner "
           "hasn't published, and months before June 2025, when Google didn't split Performance Max by network.", s["hint"])
    ws.set(4, 0, "Eligible impressions = the account's Google Search impressions ÷ its search impression share. They also move "
           "when campaigns start, stop or change targeting, so read searches for demand.", s["hint"])
    r0 = 6
    ws.set(r0, 0, "", s["hdr"])
    c = 1
    for comp in sv["comparisons"]:
        ws.set(r0, c, "%s: %s" % (comp["name"], comp["prior"]), s["hdr"])
        ws.set(r0, c + 1, "%s: %s" % (comp["name"], comp["current"]), s["hdr"])
        ws.set(r0, c + 2, "Change", s["hdr"])
        c += 3
    ws.height(r0, 44)
    labels = ["Avg monthly searches", "Avg eligible impressions"] if sv["has_eligible"] else ["Avg monthly searches"]
    for i, label in enumerate(labels):
        ws.set(r0 + 1 + i, 0, label, s["label"])
        c = 1
        for comp in sv["comparisons"]:
            _, prior, cur, chg = comp["rows"][i]
            ws.set(r0 + 1 + i, c, prior if prior is not None else "n/a", s["int"] if prior is not None else s["right_i"])
            ws.set(r0 + 1 + i, c + 1, cur if cur is not None else "n/a", s["int"] if cur is not None else s["right_i"])
            ws.set(r0 + 1 + i, c + 2, chg if chg is not None else "n/a", s["pct0"] if chg is not None else s["right_i"])
            c += 3
    tr = 23
    ws.set(tr, 0, "Month", s["hdr"])
    ws.set(tr, 1, "Total searches", s["hdr"])
    ws.set(tr, 2, "Eligible impressions", s["hdr"])
    for j, k in enumerate(kws):
        ws.set(tr, 3 + j, k, s["hdr"])
    ws.height(tr, 44)
    for i, m in enumerate(sv["months"]):
        r = tr + 1 + i
        ws.set(r, 0, Text(month_label(m)), s["text_l"])
        t = sv["total"](m)
        ws.set(r, 1, t if t is not None else "", s["int"])
        e = sv["eligible"](m) if sv["has_eligible"] else None
        ws.set(r, 2, e if e is not None else "", s["int"])
        for j, k in enumerate(kws):
            v = sv["kw"](k, m)
            ws.set(r, 3 + j, v if v is not None else "", s["int"])
    last = tr + len(sv["months"])
    ws.conditional(rng(tr + 1, 0, last, 2 + len(kws)), "ISEVEN(ROW())", bk.dx_band)
    cat = "%s!$A$%d:$A$%d" % (ws.q, tr + 2, last + 1)
    ws.chart(9, 0, 520, 240, line_chart("Monthly Google searches (Keyword Planner)", cat,
                                         [("Total searches", "%s!$B$%d:$B$%d" % (ws.q, tr + 2, last + 1), "C27BA0")],
                                         date_fmt=None))
    if sv["has_eligible"]:
        ws.chart(9, 4, 520, 240, line_chart("Impressions the account was eligible for (Google Search)", cat,
                                             [("Eligible impressions", "%s!$C$%d:$C$%d" % (ws.q, tr + 2, last + 1), BLUE)],
                                             date_fmt=None), dx=70)
    ws.width(0, 26)
    for j in range(1, 3 + len(kws)):
        ws.width(j, 15)
    ws.freeze = (0, 1)
    return ws


# ---- Channel Split tab ------------------------------------------------------------------------
def tab_channel_split(bk, camps, meta):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Channel Split", tab=TABS["channel"])
    cd = wb.sheet("Channel Data", hidden=True)
    td = wb.sheet("Trend Data", hidden=True)
    q, qt = cd.q, td.q
    has_other = any(c["ch"][OTHER_CH]["cost"] > 0 or c["ch"][OTHER_CH]["conv"] > 0 for c in camps)
    table_ch = TABLE_CHANNELS if has_other else TABLE_CHANNELS[:-1]
    # Channel totals per filter: rows Filter|Channel
    cd.row(0, 0, ["Key", "Cost", "Conversions", "Conv. value"])
    r = 1
    per_filter = {}
    for f in FILTERS:
        tot = {k: blank() for k in TABLE_CHANNELS}
        lst = [c for c in camps if in_filter(c, f)]
        for c in lst:
            for k in TABLE_CHANNELS:
                add_raw(tot[k], c["ch"][k])
        per_filter[f] = (tot, cap_campaigns(lst))
        for k in TABLE_CHANNELS:
            cd.row(r, 0, [Text("%s|%s" % (f, k)), tot[k]["cost"], tot[k]["conv"], tot[k]["val"]])
            r += 1
    # Campaign rows per filter: Filter|rank
    n_camp = max(1, max(len(per_filter[f][1]) for f in FILTERS))
    cd.row(0, 6, ["Key", "Campaign", "Cost", "Conversions"] + ["Cost: " + k for k in CHANNELS] + ["Conv: " + k for k in CHANNELS])
    r = 1
    for f in FILTERS:
        for i, c in enumerate(per_filter[f][1]):
            cd.row(r, 6, [Text("%s|%d" % (f, i + 1)), Text(c["name"]), c["total"]["cost"], c["total"]["conv"]]
                   + [c["ch"][k]["cost"] for k in CHANNELS] + [c["ch"][k]["conv"] for k in CHANNELS])
            r += 1
    camp_last = max(r, 2)
    # Daily trend rows per filter: Filter|serial
    all_days, mapper, unit = trend_periods(meta)
    rolled = {c["id"]: roll_days(c["days"], mapper) for c in camps}
    td.row(0, 0, ["Key"] + ["Cost: " + k for k in CHANNELS] + ["Conv: " + k for k in CHANNELS])
    r = 1
    for f in FILTERS:
        lst = [c for c in camps if in_filter(c, f)]
        for d in all_days:
            vals = [0.0] * 12
            for c in lst:
                ch = rolled[c["id"]].get(d)
                if ch:
                    for j, k in enumerate(CHANNELS):
                        vals[j] += ch[k]["cost"]
                        vals[6 + j] += ch[k]["conv"]
            td.row(r, 0, [Text("%s|%s" % (f, d))] + vals)
            r += 1
    trend_last = r
    # Visible tab
    bk.banner(ws, "", bk.subtitle(fmt_range(meta)), 13)
    ws.set(0, 0, '="%s — "&$B$4&" Channel Performance"' % bk.store.replace('"', '""'), s["banner"])
    ws.set(3, 0, "Filter:", s["chip"])
    ws.merge(3, 1, 3, 2, FILTERS[0], s["drop"])
    ws.dropdown(3, 1, FILTERS)
    ws.set(3, 3, "👈 PMax + Shopping, PMax only, or every campaign type", s["hint"])
    ws.height(3, 24)
    # Channel table at rows 20+
    t0 = 19
    ws.row(t0, 0, ["Channel", "Cost", "Conversions", "Conv. value", "ROAS", "Share of cost"], s["hdr"])
    for i, k in enumerate(table_ch):
        rr = t0 + 1 + i
        ws.set(rr, 0, Text(k), s["text_l"])
        for c, col in ((1, "B"), (2, "C"), (3, "D")):
            ws.set(rr, c, '=IFERROR(INDEX(%s!$%s$2:$%s$%d,MATCH($B$4&"|"&$A%d,%s!$A$2:$A$%d,0)),0)'
                   % (q, col, col, 1 + 3 * len(TABLE_CHANNELS), rr + 1, q, 1 + 3 * len(TABLE_CHANNELS)),
                   [None, s["money"], s["dec"], s["money"]][c])
        ws.set(rr, 4, '=IFERROR(D%d/B%d,0)' % (rr + 1, rr + 1), s["roas"])
        ws.set(rr, 5, '=IFERROR(B%d/$B$%d,0)' % (rr + 1, t0 + 2 + len(table_ch)), s["pct"])
    tr = t0 + 1 + len(table_ch)
    ws.set(tr, 0, "TOTAL", s["bold"])
    for c, st in ((1, "money"), (2, "dec"), (3, "money")):
        ws.set(tr, c, "=SUM(%s)" % rng(t0 + 1, c, tr - 1, c), bk.wb.style(bold=True, fmt={"money": bk.money(2), "dec": "#,##0.00"}[st]))
    ws.set(tr, 4, '=IFERROR(D%d/B%d,0)' % (tr + 1, tr + 1), bk.wb.style(bold=True, fmt='0.00"x"'))
    ws.set(tr, 5, '=IFERROR(B%d/B%d,0)' % (tr + 1, tr + 1), bk.wb.style(bold=True, fmt="0.0%"))
    ws.conditional(rng(t0 + 1, 0, tr, 5), '$A%d="TOTAL"' % (t0 + 2), bk.dx_total)
    ws.conditional(rng(t0 + 1, 0, tr - 1, 5), 'ISEVEN(ROW())', bk.dx_band)
    if has_other:
        ws.set(tr + 1, 0, "Cross-network & other: Performance Max spend Google reported without a network (before June 2025), "
               "plus any network type this report doesn't name.", s["hint"])
    # Chart data block on the visible tab, far right (hidden columns would hide chart data in Sheets): use Chart Data sheet
    ch = wb.sheet("Chart Data", hidden=True)
    qc = ch.q
    ch.row(0, 0, ["Channel", "Cost", "Conversions"])
    for i, k in enumerate(CHANNELS):
        ch.set(1 + i, 0, Text(k))
        ch.set(1 + i, 1, "=%s!B%d" % (ws.q, t0 + 2 + table_ch.index(k)))
        ch.set(1 + i, 2, "=%s!C%d" % (ws.q, t0 + 2 + table_ch.index(k)))
    ch.row(0, 4, ["#", "Campaign", "Cost", "Conversions"] + ["Cost: " + k for k in CHANNELS] + ["Conv: " + k for k in CHANNELS])
    for i in range(n_camp):
        rr = 1 + i
        ch.set(rr, 4, i + 1)
        ch.set(rr, 23, '=IFERROR(MATCH(%s!$B$4&"|"&E%d,%s!$G$2:$G$%d,0),"")' % (ws.q, rr + 1, q, camp_last))
        for j in range(15):
            src = col_letter(7 + j)
            ch.set(rr, 5 + j, '=IF($X%d="","",INDEX(%s!$%s$2:$%s$%d,$X%d))' % (rr + 1, q, src, src, camp_last, rr + 1))
    n_days = len(all_days)
    ch.row(0, 25, ["Date"] + CHANNELS + ["Conv: " + k for k in CHANNELS])
    for i, d in enumerate(all_days):
        rr = 1 + i
        ch.set(rr, 25, (dt.date.fromisoformat(d) - dt.date(1899, 12, 30)).days, s["date_short"])
        ch.set(rr, 38, '=IFERROR(MATCH(%s!$B$4&"|"&"%s",%s!$A$2:$A$%d,0),"")' % (ws.q, d, qt, trend_last))
        for j in range(12):
            src = col_letter(1 + j)
            ch.set(rr, 26 + j, '=IF($AM%d="",0,INDEX(%s!$%s$2:$%s$%d,$AM%d))' % (rr + 1, qt, src, src, trend_last, rr + 1))
    colors = [CH_COLOR[k] for k in CHANNELS]
    ws.chart(5, 0, 300, 230, doughnut_chart("Cost by Channel", "%s!$A$2:$A$7" % qc, "%s!$B$2:$B$7" % qc, colors))
    ws.chart(5, 2, 300, 230, doughnut_chart("Conversions by Channel", "%s!$A$2:$A$7" % qc, "%s!$C$2:$C$7" % qc, colors), dx=40)
    cr = "%s!$F$2:$F$%d" % (qc, n_camp + 1)
    ccolors = [CAMPAIGN_COLORS[i % len(CAMPAIGN_COLORS)] for i in range(n_camp)]
    ws.chart(3, 7, 420, 250, doughnut_chart("Cost by Campaign", cr, "%s!$G$2:$G$%d" % (qc, n_camp + 1), ccolors), dy=10)
    ws.chart(18, 7, 420, 250, doughnut_chart("Conversions by Campaign", cr, "%s!$H$2:$H$%d" % (qc, n_camp + 1), ccolors), dy=10)
    bar_h = max(260, 60 + 28 * n_camp)
    cost_series = [(k, "%s!$%s$2:$%s$%d" % (qc, col_letter(8 + j), col_letter(8 + j), n_camp + 1), CH_COLOR[k]) for j, k in enumerate(CHANNELS)]
    conv_series = [(k, "%s!$%s$2:$%s$%d" % (qc, col_letter(14 + j), col_letter(14 + j), n_camp + 1), CH_COLOR[k]) for j, k in enumerate(CHANNELS)]
    ws.chart(33, 7, 520, bar_h, stacked_bar_chart("Channel Split by Campaign — Cost", cr, cost_series, bk.money(0)))
    ws.chart(33 + bar_h // 20 + 2, 7, 520, bar_h, stacked_bar_chart("Channel Split by Campaign — Conversions", cr, conv_series, "#,##0"))
    dates = "%s!$Z$2:$Z$%d" % (qc, n_days + 1)
    per = " (weekly)" if unit == "week" else ""
    ws.chart(32, 0, 640, 280, line_chart("Spend by Channel Over Time" + per, dates,
                                         [(k, "%s!$%s$2:$%s$%d" % (qc, col_letter(26 + j), col_letter(26 + j), n_days + 1), CH_COLOR[k]) for j, k in enumerate(CHANNELS)],
                                         bk.money(0)))
    ws.chart(48, 0, 640, 280, line_chart("Conversions by Channel Over Time" + per, dates,
                                         [(k, "%s!$%s$2:$%s$%d" % (qc, col_letter(32 + j), col_letter(32 + j), n_days + 1), CH_COLOR[k]) for j, k in enumerate(CHANNELS)],
                                         "#,##0"))
    for c, w in enumerate([24, 14, 13, 14, 10, 11, 4]):
        ws.width(c, w)
    for c in range(7, 13):
        ws.width(c, 12)
    return ws, per_filter


# ---- Campaign tab -----------------------------------------------------------------------------
def tab_campaign(bk, camps, meta):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Campaign", tab=TABS["campaign"])
    data = wb.sheet("Campaign Data", hidden=True)
    q = data.q
    names = [c["name"] for c in camps]
    lst = bk.add_list(names)
    data.row(0, 0, ["#", "Channel", "Cost", "Conversions", "Conv. value"])
    r = 1
    for i, c in enumerate(camps):
        for k in TABLE_CHANNELS:
            data.row(r, 0, [i + 1, Text(k), c["ch"][k]["cost"], c["ch"][k]["conv"], c["ch"][k]["val"]])
            r += 1
    ch_last = max(r, 2)
    all_days, mapper, unit = trend_periods(meta)
    data.row(0, 6, ["Key"] + ["Cost: " + k for k in CHANNELS] + ["Conv: " + k for k in CHANNELS])
    r = 1
    for i, c in enumerate(camps):
        rolled = roll_days(c["days"], mapper)
        for d in sorted(rolled):
            x = rolled[d]
            data.row(r, 6, [Text("%d|%s" % (i + 1, d))] + [x[k]["cost"] for k in CHANNELS] + [x[k]["conv"] for k in CHANNELS])
            r += 1
    tr_last = max(r, 2)
    bk.banner(ws, "", bk.subtitle(fmt_range(meta)), 13)
    ws.set(0, 0, '="%s — "&$B$4' % bk.store.replace('"', '""'), s["banner"])
    ws.set(3, 0, "Campaign:", s["chip"])
    ws.merge(3, 1, 3, 4, names[0] if names else "", s["drop"])
    ws.dropdown(3, 1, lst)
    ws.set(3, 5, "👈 pick any campaign", s["hint"])
    ws.set(3, 9, '=IFERROR(MATCH($B$4,%s,0),0)' % lst, s["ghost"])
    ws.height(3, 24)
    ws.set(4, 0, '="Campaign type: "&IFERROR(INDEX(%s!$A$1:$A$%d,$J$4),"")' % (quote_sheet("Campaign Types"), len(camps)), s["hint"])
    types = wb.sheet("Campaign Types", hidden=True)
    for i, c in enumerate(camps):
        types.set(i, 0, Text(TYPE_LABEL.get(c["type"], c["type"].replace("_", " ").title())))
    t0 = 19
    ws.row(t0, 0, ["Channel", "Cost", "Conversions", "Conv. value", "ROAS", "Share of cost"], s["hdr"])
    for i, k in enumerate(TABLE_CHANNELS):
        rr = t0 + 1 + i
        ws.set(rr, 0, Text(k), s["text_l"])
        for c, col in ((1, "C"), (2, "D"), (3, "E")):
            ws.set(rr, c, '=SUMIFS(%s!$%s$2:$%s$%d,%s!$A$2:$A$%d,$J$4,%s!$B$2:$B$%d,$A%d)'
                   % (q, col, col, ch_last, q, ch_last, q, ch_last, rr + 1), [None, s["money"], s["dec"], s["money"]][c])
        ws.set(rr, 4, '=IFERROR(D%d/B%d,0)' % (rr + 1, rr + 1), s["roas"])
        ws.set(rr, 5, '=IFERROR(B%d/$B$%d,0)' % (rr + 1, t0 + 2 + len(TABLE_CHANNELS)), s["pct"])
    tr = t0 + 1 + len(TABLE_CHANNELS)
    ws.set(tr, 0, "TOTAL", s["bold"])
    for c, fmt in ((1, bk.money(2)), (2, "#,##0.00"), (3, bk.money(2))):
        ws.set(tr, c, "=SUM(%s)" % rng(t0 + 1, c, tr - 1, c), wb.style(bold=True, fmt=fmt))
    ws.set(tr, 4, '=IFERROR(D%d/B%d,0)' % (tr + 1, tr + 1), wb.style(bold=True, fmt='0.00"x"'))
    ws.set(tr, 5, '=IFERROR(B%d/B%d,0)' % (tr + 1, tr + 1), wb.style(bold=True, fmt="0.0%"))
    ws.conditional(rng(t0 + 1, 0, tr, 5), '$A%d="TOTAL"' % (t0 + 2), bk.dx_total)
    ws.conditional(rng(t0 + 1, 0, tr - 1, 5), 'ISEVEN(ROW())', bk.dx_band)
    ch = wb.sheet("Campaign Chart Data", hidden=True)
    qc = ch.q
    ch.row(0, 0, ["Channel", "Cost", "Conversions"])
    for i, k in enumerate(CHANNELS):
        ch.set(1 + i, 0, Text(k))
        ch.set(1 + i, 1, "=%s!B%d" % (ws.q, t0 + 2 + i))
        ch.set(1 + i, 2, "=%s!C%d" % (ws.q, t0 + 2 + i))
    ch.row(0, 4, ["Date"] + CHANNELS + ["Conv: " + k for k in CHANNELS])
    for i, d in enumerate(all_days):
        rr = 1 + i
        ch.set(rr, 4, (dt.date.fromisoformat(d) - dt.date(1899, 12, 30)).days, s["date_short"])
        ch.set(rr, 17, '=IFERROR(MATCH(%s!$J$4&"|"&"%s",%s!$G$2:$G$%d,0),"")' % (ws.q, d, q, tr_last))
        for j in range(12):
            src = col_letter(7 + j)
            ch.set(rr, 5 + j, '=IF($R%d="",0,INDEX(%s!$%s$2:$%s$%d,$R%d))' % (rr + 1, q, src, src, tr_last, rr + 1))
    colors = [CH_COLOR[k] for k in CHANNELS]
    ws.chart(5, 0, 300, 230, doughnut_chart("Cost by Channel", "%s!$A$2:$A$7" % qc, "%s!$B$2:$B$7" % qc, colors))
    ws.chart(5, 2, 300, 230, doughnut_chart("Conversions by Channel", "%s!$A$2:$A$7" % qc, "%s!$C$2:$C$7" % qc, colors), dx=40)
    n_days = len(all_days)
    dates = "%s!$E$2:$E$%d" % (qc, n_days + 1)
    per = " (weekly)" if unit == "week" else ""
    ws.chart(32, 0, 640, 280, line_chart("Spend by Channel Over Time" + per, dates,
                                         [(k, "%s!$%s$2:$%s$%d" % (qc, col_letter(5 + j), col_letter(5 + j), n_days + 1), CH_COLOR[k]) for j, k in enumerate(CHANNELS)],
                                         bk.money(0)))
    ws.chart(48, 0, 640, 280, line_chart("Conversions by Channel Over Time" + per, dates,
                                         [(k, "%s!$%s$2:$%s$%d" % (qc, col_letter(11 + j), col_letter(11 + j), n_days + 1), CH_COLOR[k]) for j, k in enumerate(CHANNELS)],
                                         "#,##0"))
    for c, w in enumerate([24, 14, 13, 14, 10, 11, 4]):
        ws.width(c, w)
    ws.width(9, 2)
    return ws


# ---- Assets tab -------------------------------------------------------------------------------
def tab_assets(bk, assets, meta, cap=300):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Assets", tab=TABS["assets"])
    data = wb.sheet("Asset Data", hidden=True)
    q = data.q
    heads = ["Key", "Type", "Asset", "Source", "Field types", "Impressions", "Clicks", "Cost", "Conversions", "Conv. value", "Link"]
    data.row(0, 0, heads)
    r = 1
    counts = defaultdict(int)
    for x in assets:
        counts[x["type"]] += 1
        if counts[x["type"]] > cap:
            continue
        data.row(r, 0, [Text("%s|%d" % (x["type"], counts[x["type"]])), Text(x["type"]), Text(x["name"]), Text(x["source"]),
                        Text(x["fields"]), x["impr"], x["clicks"], x["cost"], x["conv"], x["val"], Text(x["link"])])
        r += 1
    last = max(r, 2)
    bk.banner(ws, "%s — Performance Max Assets" % bk.store, bk.subtitle(fmt_range(meta)), 15)
    ws.set(3, 0, "Type:", s["chip"])
    ws.merge(3, 1, 3, 2, "Headlines", s["drop"])
    ws.dropdown(3, 1, ASSET_TYPES)
    ws.set(3, 3, "👈 headlines, long headlines, descriptions, images or videos", s["hint"])
    ws.height(3, 24)
    ws.set(4, 0, "Assets show together in one ad, so their numbers overlap: read them to compare assets of the same type, "
           "not to add up. Sorted by impressions.", s["hint"])
    # Summary by type, in the same columns as the table below
    ws.row(6, 1, ["Asset type", "Assets", "Impressions", "Clicks", "CTR", "Cost", "Conversions", "Conv. rate", "Conv. value", "ROAS"], s["hdr"])
    for i, t in enumerate(ASSET_TYPES):
        rr = 7 + i
        R = rr + 1
        mine = [x for x in assets if x["type"] == t]
        ws.set(rr, 1, Text(t), s["text_l"])
        ws.set(rr, 2, len(mine), s["int"])
        ws.set(rr, 3, sum(x["impr"] for x in mine), s["int"])
        ws.set(rr, 4, sum(x["clicks"] for x in mine), s["int"])
        ws.set(rr, 5, '=IFERROR(E%d/D%d,0)' % (R, R), s["pct2"])
        ws.set(rr, 6, sum(x["cost"] for x in mine), s["money"])
        ws.set(rr, 7, sum(x["conv"] for x in mine), s["dec"])
        ws.set(rr, 8, '=IFERROR(H%d/E%d,0)' % (R, R), s["pct2"])
        ws.set(rr, 9, sum(x["val"] for x in mine), s["money"])
        ws.set(rr, 10, '=IFERROR(J%d/G%d,0)' % (R, R), s["roas"])
    ws.conditional(rng(7, 1, 11, 10), '$B8=$B$4', wb.dxf(bold=True, fill="FFF2CC"))
    t0 = 13
    cols = ["#", "Asset", "Source", "Impressions", "Clicks", "CTR", "Cost", "Conversions", "Conv. rate", "Conv. value",
            "ROAS", "Cost / conv.", "Link"]
    ws.row(t0, 0, cols, s["hdr"])
    ws.height(t0, 30)
    n = min(cap, max(counts.values()) if counts else 1)
    for k in range(1, n + 1):
        rr = t0 + k
        R = rr + 1
        ws.set(rr, 0, k, s["int"])
        ws.set(rr, 14, '=IFERROR(MATCH($B$4&"|"&$A%d,%s!$A$2:$A$%d,0),"")' % (R, q, last), s["ghost"])
        for c, src, st in ((1, "C", "wrap"), (2, "D", "text"), (3, "F", "int"), (4, "G", "int"), (6, "H", "money"),
                           (7, "I", "dec"), (9, "J", "money")):
            ws.set(rr, c, '=IF($O%d="","",INDEX(%s!$%s$2:$%s$%d,$O%d))' % (R, q, src, src, last, R), s[st])
        ws.set(rr, 5, '=IF($O%d="","",IFERROR(E%d/D%d,0))' % (R, R, R), s["pct2"])
        ws.set(rr, 8, '=IF($O%d="","",IFERROR(H%d/E%d,0))' % (R, R, R), s["pct2"])
        ws.set(rr, 10, '=IF($O%d="","",IFERROR(J%d/G%d,0))' % (R, R, R), s["roas"])
        ws.set(rr, 11, '=IF($O%d="","",IFERROR(G%d/H%d,0))' % (R, R, R), s["money"])
        ws.set(rr, 12, '=IF($O%d="","",IF(INDEX(%s!$K$2:$K$%d,$O%d)="","",HYPERLINK(INDEX(%s!$K$2:$K$%d,$O%d),"Open")))'
               % (R, q, last, R, q, last, R), s["link"])
    ws.conditional(rng(t0 + 1, 0, t0 + n, 12), 'AND($O%d<>"",ISEVEN(ROW()))' % (t0 + 2), bk.dx_band)
    for c, w in enumerate([6, 60, 18, 12, 10, 9, 12, 12, 10, 13, 9, 11, 8, 2, 3]):
        ws.width(c, w)
    return ws


# ---- Product tabs -----------------------------------------------------------------------------
def product_tab(bk, name, data_name, tab_color, items, meta, roas_t, cost_t, id_label, is_family, cap=1000):
    """items: dicts with id(label), title, count, feeds, statuses, impr, clicks, cost, conv, val."""
    wb, s = bk.wb, bk.s
    ws = wb.sheet(name, tab=tab_color)
    data = wb.sheet(data_name, hidden=True)
    q, wq = data.q, ws.q
    n = len(items)
    last = n + 1
    # Data: A label, B title/count, C feeds, D statuses, E impr, F clicks, G cost, H conv, I val, J CTR, K CVR, L ROAS,
    # M bucket (live), N sort key (live)
    data.row(0, 0, [id_label, "Title" if not is_family else "Products", "Feed labels", "Statuses", "Impressions", "Clicks",
                    "Cost", "Conversions", "Conv. value", "CTR", "Conv. rate", "ROAS", "Bucket", "Sort key"])
    for i, x in enumerate(items):
        r = i + 1
        R = r + 1
        data.row(r, 0, [Text(x["id"]), Text(x["title"]) if not is_family else x["count"], Text(x["feeds"]), Text(x["statuses"]),
                        x["impr"], x["clicks"], x["cost"], x["conv"], x["val"],
                        safe_div(x["clicks"], x["impr"]), safe_div(x["conv"], x["clicks"]), safe_div(x["val"], x["cost"])])
        data.set(r, 12, '=IF(G%d=0,"Zombies",IF(G%d<%s!$L$6,"Low spend",IF(L%d>=%s!$L$5,"Profitable","Costly")))' % (R, R, wq, R, wq))
        data.set(r, 13, '=IF(OR(%s!$B$19="All",M%d=%s!$B$19),IF(%s!$H$19="Descending",1,-1)*CHOOSE(%s!$V$19,G%d,H%d,I%d,L%d,F%d,E%d,J%d,K%d)+ROW()*1E-7,"")'
                 % (wq, R, wq, wq, wq, R, R, R, R, R, R, R, R))
    plural = "Families" if is_family else "Products"
    bk.banner(ws, "%s — %s by Bucket" % (bk.store, "Product Families" if is_family else "Products"),
              bk.subtitle(fmt_range(meta) + "   ·   Shopping and the Shopping part of Performance Max"), 15)
    # Settings block K4:L7
    ws.set(3, 10, "Date range", s["label"])
    ws.merge(3, 11, 3, 12, fmt_range(meta), s["text"])
    ws.set(4, 10, "ROAS threshold", s["label"])
    ws.set(4, 11, roas_t, wb.style(bold=True, fill=CREAM, h="center", fmt="0%", border={"left": "thin", "right": "thin", "top": "thin", "bottom": "thin", "color": "BF9000"}))
    ws.set(5, 10, "Cost threshold", s["label"])
    ws.set(5, 11, cost_t, s["drop_money"])
    ws.set(6, 10, "Gross margin %", s["label"])
    ws.set(6, 11, bk.margin, s["drop_pct"])
    ws.set(4, 12, "👈 edit the cream cells: buckets, charts and the table all update", s["hint"])
    # Bucket summary K9:S13
    hdr = ["Bucket", plural, "%% of %s" % plural.lower(), "Cost", "% of cost", "Conv. value", "ROAS", "Profit", "POAS"]
    ws.row(8, 10, hdr, s["hdr"])
    ws.height(8, 30)
    for i, b in enumerate(BUCKETS):
        rr = 9 + i
        R = rr + 1
        ws.set(rr, 10, Text(b), wb.style(bold=True, fill=BUCKET_FILL[b], indent=1))
        ws.set(rr, 11, '=COUNTIF(%s!$M$2:$M$%d,$K%d)' % (q, last, R), s["int"])
        ws.set(rr, 12, '=IFERROR(L%d/$L$14,0)' % R, s["pct"])
        ws.set(rr, 13, '=SUMIFS(%s!$G$2:$G$%d,%s!$M$2:$M$%d,$K%d)' % (q, last, q, last, R), s["money0"])
        ws.set(rr, 14, '=IFERROR(N%d/$N$14,0)' % R, s["pct"])
        ws.set(rr, 15, '=SUMIFS(%s!$I$2:$I$%d,%s!$M$2:$M$%d,$K%d)' % (q, last, q, last, R), s["money0"])
        ws.set(rr, 16, '=IFERROR(P%d/N%d,0)' % (R, R), s["roas"])
        ws.set(rr, 17, '=P%d*$L$7-N%d' % (R, R), s["money0"])
        ws.set(rr, 18, '=IFERROR(R%d/N%d,0)' % (R, R), s["pct0"])
    ws.set(13, 10, "Total", wb.style(bold=True, fill=TOTAL, indent=1))
    for c, col, fmt in ((11, "L", "#,##0"), (12, "M", "0.0%"), (13, "N", bk.money(0)), (14, "O", "0.0%"), (15, "P", bk.money(0)),
                        (17, "R", bk.money(0))):
        ws.set(13, c, "=SUM(%s10:%s13)" % (col, col), wb.style(bold=True, fill=TOTAL, fmt=fmt))
    ws.set(13, 16, "=IFERROR(P14/N14,0)", wb.style(bold=True, fill=TOTAL, fmt='0.00"x"'))
    ws.set(13, 18, "=IFERROR(R14/N14,0)", wb.style(bold=True, fill=TOTAL, fmt="0%"))
    ws.set(14, 10, "Profitable: cost ≥ threshold, ROAS ≥ threshold. Costly: cost ≥ threshold, ROAS below it. Low spend: some cost, "
           "below the threshold. Zombies: no spend. Profit = conv. value × margin − cost; POAS = profit ÷ cost.", s["hint"])
    colors = [BUCKET_CHART[b] for b in BUCKETS]
    cat = "%s!$K$10:$K$13" % wq
    ws.chart(3, 0, 290, 225, doughnut_chart("%s by Bucket" % plural, cat, "%s!$L$10:$L$13" % wq, colors))
    ws.chart(3, 3, 290, 225, doughnut_chart("Cost by Bucket", cat, "%s!$N$10:$N$13" % wq, colors), dx=10)
    ws.chart(3, 6, 290, 225, doughnut_chart("Conv. Value by Bucket", cat, "%s!$P$10:$P$13" % wq, colors), dx=20)
    # Controls row 19
    rc = 18
    ws.set(rc, 0, "Bucket:", s["chip"])
    ws.merge(rc, 1, rc, 2, "Profitable", s["drop"])
    ws.dropdown(rc, 1, ["All"] + BUCKETS)
    ws.set(rc, 4, "Sort by:", s["chip"])
    ws.merge(rc, 5, rc, 6, "Cost", s["drop"])
    ws.dropdown(rc, 5, SORT_METRICS)
    ws.merge(rc, 7, rc, 8, "Descending", s["drop"])
    ws.dropdown(rc, 7, ["Descending", "Ascending"])
    ws.set(rc, 9, "Rows:", s["chip"])
    rows_cap = min(cap, max(n, 1))
    ws.set(rc, 10, min(50, rows_cap), s["drop"])
    ws.number_rule(rc, 10, 1, rows_cap)
    ws.set(rc, 21, '=MATCH($F$19,{%s},0)' % ",".join('"%s"' % m for m in SORT_METRICS), s["ghost"])
    ws.set(rc, 11, "👈 pick a bucket, a sort and how many rows", s["hint"])
    ws.height(rc, 26)
    t0 = 20
    if is_family:
        cols = ["#", "Product family", "Products", "Impressions", "Clicks", "CTR", "Cost", "Conversions", "Conv. rate",
                "Conv. value", "ROAS", "Bucket"]
        srcs = [None, "A", "B", "E", "F", "J", "G", "H", "K", "I", "L", "M"]
        sts = ["int", "text", "int", "int", "int", "pct2", "money", "dec", "pct2", "money", "roas", "text"]
    else:
        cols = ["#", "Product ID", "Title", "Feed labels", "Status", "Impressions", "Clicks", "CTR", "Cost", "Conversions",
                "Conv. rate", "Conv. value", "ROAS", "Bucket"]
        srcs = [None, "A", "B", "C", "D", "E", "F", "J", "G", "H", "K", "I", "L", "M"]
        sts = ["int", "text", "text", "text", "text", "int", "int", "pct2", "money", "dec", "pct2", "money", "roas", "text"]
    ws.row(t0 - 1, 0, cols, s["hdr"])
    ws.height(t0 - 1, 30)
    helper = 20  # column U: the matched data row, kept clear of the bucket summary (K:S)
    hcol = col_letter(helper)
    key = "%s!$N$2:$N$%d" % (q, last)
    for k in range(1, rows_cap + 1):
        rr = t0 + k - 1
        R = rr + 1
        ws.set(rr, 0, '=IF(%d>$K$19,"",IF($%s%d="","",%d))' % (k, hcol, R, k), s["int"])
        ws.set(rr, helper, '=IF(%d>$K$19,"",IFERROR(MATCH(LARGE(%s,%d),%s,0),""))' % (k, key, k, key), s["ghost"])
        for c in range(1, len(cols)):
            ws.set(rr, c, '=IF($%s%d="","",INDEX(%s!$%s$2:$%s$%d,$%s%d))' % (hcol, R, q, srcs[c], srcs[c], last, hcol, R), s[sts[c]])
    end = t0 + rows_cap - 1
    for b in BUCKETS:
        ws.conditional(rng(t0, len(cols) - 1, end, len(cols) - 1), '$%s%d="%s"' % (col_letter(len(cols) - 1), t0 + 1, b),
                       wb.dxf(bold=True, fill=BUCKET_FILL[b]))
    ws.conditional(rng(t0, 0, end, len(cols) - 2), 'AND($A%d<>"",ISEVEN(ROW()))' % (t0 + 1), bk.dx_band)
    widths = [6, 40, 10, 12, 10, 9, 12, 12, 10, 13, 15, 12] if is_family else [6, 30, 46, 11, 14, 12, 10, 9, 12, 12, 15, 13, 9, 12]
    for c, w in enumerate(widths):
        ws.width(c, w)
    for c in range(len(widths), 19):
        ws.width(c, 12)
    ws.width(helper, 3)
    ws.width(21, 3)
    return ws


def tab_mapping(bk, fam_rows, meta):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Product Mapping", tab=TABS["mapping"])
    bk.banner(ws, "%s — Product Mapping" % bk.store, bk.subtitle("Which product IDs make up each product family"), 4)
    ws.set(3, 0, "To regroup products, ask Claude to change the families and rebuild (the family totals are calculated "
           "when the workbook is built).", s["hint"])
    ws.row(5, 0, ["Product family", "Product ID", "Title", "Cost"], s["hdr"])
    for i, r in enumerate(fam_rows):
        ws.row(6 + i, 0, [Text(r["family"]), Text(r["id"]), Text(r["title"]), r["cost"]], [s["text_l"], s["text"], s["text"], s["money"]])
    ws.autofilter = rng(5, 0, 5 + len(fam_rows), 3)
    ws.conditional(rng(6, 0, 5 + len(fam_rows), 3), "ISEVEN(ROW())", bk.dx_band)
    for c, w in enumerate([40, 30, 70, 12]):
        ws.width(c, w)
    ws.freeze = (6, 0)
    return ws


# ---- Keyword Gap tab --------------------------------------------------------------------------
def tab_keyword_gap(bk, gaps, meta):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Keyword Gap", tab=TABS["gap"])
    bk.banner(ws, "%s — Keyword Gap" % bk.store, bk.subtitle(fmt_range(meta)), 10)
    ws.set(3, 0, "Search terms that converted in Performance Max, checked against every Search keyword in the account "
           "(exact spelling, any match type, including paused and removed ones).", s["hint"])
    ws.set(4, 0, "Missing keyword: no Search keyword matches, so you can't bid on or control this search. Not eligible: a matching "
           "keyword exists but can't show (paused, removed, limited or in a paused campaign or ad group).", s["hint"])
    ws.row(6, 0, ["Issue", "Search terms", "Conversions", "Conv. value", "Cost"], s["hdr"])
    red, amber = "F4CCCC", "FCE5CD"
    for i, (issue, fill) in enumerate((("Missing keyword", red), ("Not eligible", amber))):
        g = [x for x in gaps if x["issue"] == issue]
        ws.row(7 + i, 0, [issue, len(g), sum(x["conv"] for x in g), sum(x["val"] for x in g), sum(x["cost"] for x in g)],
               [wb.style(bold=True, fill=fill, indent=1), s["int"], s["dec"], s["money0"], s["money0"]])
    ws.row(9, 0, ["Total", len(gaps), sum(x["conv"] for x in gaps), sum(x["val"] for x in gaps), sum(x["cost"] for x in gaps)],
           [wb.style(bold=True, fill=TOTAL, indent=1), wb.style(bold=True, fill=TOTAL, fmt="#,##0"),
            wb.style(bold=True, fill=TOTAL, fmt="#,##0.00"), wb.style(bold=True, fill=TOTAL, fmt=bk.money(0)),
            wb.style(bold=True, fill=TOTAL, fmt=bk.money(0))])
    t0 = 11
    cols = ["Search term", "Issue", "Keyword status", "Action", "Conversions", "Conv. value", "Cost", "Clicks", "Impressions", "Conv. rate"]
    ws.row(t0, 0, cols, s["hdr"])
    ws.height(t0, 30)
    for i, g in enumerate(gaps):
        r = t0 + 1 + i
        ws.row(r, 0, [Text(g["term"]), g["issue"], Text(g["status"]), g["action"], g["conv"], g["val"], g["cost"], g["clicks"],
                      g["impr"], safe_div(g["conv"], g["clicks"])],
               [s["text_l"], s["text"], s["text"], s["text"], s["dec"], s["money"], s["money"], s["int"], s["int"], s["pct2"]])
    if gaps:
        end = t0 + len(gaps)
        ws.autofilter = rng(t0, 0, end, len(cols) - 1)
        ws.conditional(rng(t0 + 1, 0, end, len(cols) - 1), '$B%d="Missing keyword"' % (t0 + 2), wb.dxf(fill="FBE3E3"))
        ws.conditional(rng(t0 + 1, 0, end, len(cols) - 1), '$B%d="Not eligible"' % (t0 + 2), wb.dxf(fill="FDF0E1"))
    else:
        ws.set(t0 + 1, 0, "No gaps: every converting Performance Max search term has an eligible Search keyword.", s["hint"])
    for c, w in enumerate([44, 17, 44, 24, 12, 13, 12, 10, 12, 11]):
        ws.width(c, w)
    ws.freeze = (t0 + 1, 1)
    return ws


# ---- Start Here tab ---------------------------------------------------------------------------
def tab_start(bk, facts, tabs_built, badge):
    wb, s = bk.wb, bk.s
    ws = wb.sheet("Start Here", tab=TABS["start"])
    ws.merge(0, 0, 0, 7, "      Google Ads Audit Analysis", wb.style(bold=True, color="FFFFFF", fill=NAVY, size=16))
    ws.height(0, 36)
    if badge:
        ws.picture(0, 0, 28, 28, wb.add_media(badge), dx=6, dy=4, name="Big Flare")
    ws.merge(1, 0, 1, 7, "%s   ·   %s" % (bk.store, bk.subtitle(fmt_range(bk.meta))), s["sub"])
    ws.set(2, 0, '=HYPERLINK("%s","Built with the Big Flare Skills Pack: free Claude skills for ecommerce Google Ads")' % PACK_URL, s["link"])
    r = 4
    ws.set(r, 0, "The headline numbers", s["h2"])
    r += 1
    for label, value, st in facts:
        ws.set(r, 0, label, s["label"])
        ws.merge(r, 1, r, 3, value, bk.wb.style(fmt=s_fmt(bk, st), h="left", indent=1))
        r += 1
    r += 1
    ws.set(r, 0, "What's in each tab", s["h2"])
    r += 1
    guide = [
        ("Account", "Every month of last year and this year, all campaign types: sales, ROAS, impression share and gross profit after ad spend. Start here to see whether a drop is real."),
        ("Search Volume", "Monthly Google searches for your main category keywords, so you can tell a shrinking market from a shrinking account."),
        ("Channel Split", "Where Performance Max and Shopping spend really goes: Shopping ads, Search, YouTube, Display, Gmail and Discover. Switch to Whole Account to see every campaign."),
        ("Campaign", "The same channel split for any one campaign, with daily trends."),
        ("Assets", "How each Performance Max headline, description, image and video performs."),
        ("Products", "Every product sorted into Profitable, Costly, Low spend and Zombies (no spend). Edit the thresholds and margin to re-sort."),
        ("Product Families", "The same buckets for whole products, with sizes and colours grouped together. Product Mapping shows which IDs are in each."),
        ("Keyword Gap", "Searches that convert in Performance Max but have no working Search keyword: the keywords to add or fix."),
    ]
    for name, text in guide:
        if name not in tabs_built:
            continue
        ws.set(r, 0, name, s["label"])
        ws.merge(r, 1, r, 7, text, s["wrap"])
        ws.height(r, 30)
        r += 1
    r += 1
    ws.set(r, 0, "How to use it", s["h2"])
    r += 1
    for line in ["Cream cells are yours to change: dropdowns switch what a tab shows, and margins and thresholds recalculate everything that depends on them.",
                 "Numbers come straight from your Google Ads account for the dates above. Conversions are as Google Ads counts them.",
                 "Hidden tabs hold the data the formulas read. Leave them be, or the dropdowns stop working."]:
        ws.merge(r, 0, r, 7, "•  " + line, s["wrap"])
        ws.height(r, 30)
        r += 1
    r += 1
    ws.set(r, 0, '=HYPERLINK("%s","Want Big Flare to run your Google Ads? bigflare.com")' % BF_URL, s["link"])
    ws.width(0, 44)
    for c in range(1, 8):
        ws.width(c, 16)
    return ws


def s_fmt(bk, st):
    return {"money0": bk.money(0), "money": bk.money(2), "pct": "0.0%", "roas": '0.00"x"', "dec": "#,##0.00",
            "int": "#,##0", None: None}.get(st)


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------
def cmd_build(a):
    data = load_run(a.run)
    meta, ds = data["meta"], data["datasets"]
    store = a.store or meta.get("account_name") or "Google Ads account"
    code = (meta.get("currency_code") or "").upper()
    symbol = a.currency_symbol if a.currency_symbol is not None else SYMBOLS.get(code, code + " ")
    bk = Book(store, meta, symbol)
    bk.domain = a.domain or ""
    bk.margin = a.margin
    warnings = []

    camps, unknown = aggregate_campaigns(ds)
    if not camps:
        fail("No campaign had spend or conversions in %s to %s." % (meta["date_from"], meta["date_to"]))
    if unknown:
        warnings.append("Spend on network types this report doesn't name (%s) is counted in 'Cross-network & other' so totals still add up." % ", ".join(unknown))
    if not ds.get("pmax_shopping_daily") and any(c["type"] == "PERFORMANCE_MAX" for c in camps):
        warnings.append("pmax_shopping_daily is missing, so Performance Max Shopping ads are counted as Google Search.")
    acct = account_model(ds, meta)
    sv_raw = None
    sv_path = os.path.join(a.run, "search-volume.json")
    if os.path.exists(sv_path):
        with open(sv_path, encoding="utf-8") as f:
            sv_raw = json.load(f)
    sv = search_volume_model(sv_raw, acct, meta) if sv_raw else None
    assets = aggregate_assets(ds.get("assets") or [])
    products, no_inv = aggregate_products(ds.get("products") or [], ds.get("product_inventory") or [])
    if products and no_inv:
        warnings.append("product_inventory is missing, so the Products tabs only list products that had activity (no Zombies).")
    gaps = keyword_gaps(ds.get("pmax_search_terms") or [], ds.get("search_keywords") or [])
    have_gap = "pmax_search_terms" in ds and "search_keywords" in ds

    badge = None
    bp = os.path.join(SKILL_DIR, "references", "bigflare-badge.png")
    if os.path.exists(bp):
        badge = open(bp, "rb").read()

    # Facts for Start Here (computed once, also printed for the chat summary)
    whole = blank()
    for c in camps:
        add_raw(whole, c["total"])
    ps = blank()
    for c in camps:
        if c["type"] in ("PERFORMANCE_MAX", "SHOPPING"):
            add_raw(ps, c["total"])
    ps_ch = {k: blank() for k in TABLE_CHANNELS}
    for c in camps:
        if c["type"] in ("PERFORMANCE_MAX", "SHOPPING"):
            for k in TABLE_CHANNELS:
                add_raw(ps_ch[k], c["ch"][k])
    facts = [("Report dates", fmt_range(meta), None),
             ("Whole account: cost", whole["cost"], "money0"),
             ("Whole account: conv. value", whole["val"], "money0"),
             ("Whole account: ROAS", safe_div(whole["val"], whole["cost"]), "roas"),
             ("Whole account: conversions", whole["conv"], "dec")]
    summary = {"store": store, "report_range": fmt_range(meta), "currency": code,
               "whole_account": {"cost": round(whole["cost"], 2), "conv_value": round(whole["val"], 2),
                                 "conversions": round(whole["conv"], 2), "roas": round(safe_div(whole["val"], whole["cost"]), 2)}}
    if ps["cost"] > 0:
        facts.append(("PMax + Shopping: cost", ps["cost"], "money0"))
        facts.append(("PMax + Shopping: share of spend", safe_div(ps["cost"], whole["cost"]), "pct"))
        facts.append(("PMax + Shopping: ROAS", safe_div(ps["val"], ps["cost"]), "roas"))
        chans = sorted(((k, v["cost"]) for k, v in ps_ch.items()), key=lambda kv: -kv[1])
        facts.append(("Shopping ads' share of that spend", safe_div(ps_ch["Shopping Ads"]["cost"], ps["cost"]), "pct"))
        summary["pmax_shopping"] = {"cost": round(ps["cost"], 2), "share_of_account": round(safe_div(ps["cost"], whole["cost"]), 3),
                                    "roas": round(safe_div(ps["val"], ps["cost"]), 2),
                                    "channels": {k: {"cost": round(v["cost"], 2), "share": round(safe_div(v["cost"], ps["cost"]), 3),
                                                     "roas": round(safe_div(v["val"], v["cost"]), 2)} for k, v in ps_ch.items() if v["cost"] > 0}}
    if acct:
        y = acct["year"]
        to = meta["calendar_to"]
        month_end = (dt.date.fromisoformat(to) + dt.timedelta(days=1)).day == 1
        last_full = to[:7] if month_end else shift_month(to[:7], -1)
        cur_m = [m for m, _ in acct["months"] if m.startswith(str(y)) and m <= last_full]
        mx = dict(acct["months"])
        if cur_m and all(shift_month(m, -12) in mx for m in cur_m):
            cv = sum(mx[m]["val"] for m in cur_m)
            pv = sum(mx[shift_month(m, -12)]["val"] for m in cur_m)
            cc = sum(mx[m]["cost"] for m in cur_m)
            pc = sum(mx[shift_month(m, -12)]["cost"] for m in cur_m)
            span = "%s–%s" % (MONTHS[int(cur_m[0][5:]) - 1], month_label(cur_m[-1])) if len(cur_m) > 1 else month_label(cur_m[0])

            def yoy(a_, b_):
                return "%s%s vs %s%s (%s%.0f%%)" % (symbol, format(round(a_), ","), symbol, format(round(b_), ","),
                                                   "+" if a_ >= b_ else "", (safe_div(a_, b_) - 1) * 100) if b_ else "n/a"
            facts.append(("Conv. value, %s vs a year earlier" % span, yoy(cv, pv), None))
            facts.append(("Cost, %s vs a year earlier" % span, yoy(cc, pc), None))
            summary["year_on_year"] = {"months": span, "conv_value": round(cv, 2), "conv_value_prior": round(pv, 2),
                                       "cost": round(cc, 2), "cost_prior": round(pc, 2)}
    if acct:
        def acct_row(label, x):
            gp = x["val_ct"] * a.margin - x["cost"]
            return {"period": label, "conversions": round(x["conv"], 2), "cost": round(x["cost"], 2), "conv_value": round(x["val"], 2),
                    "roas": round(safe_div(x["val"], x["cost"]), 2), "conv_value_by_conv_time": round(x["val_ct"], 2),
                    "gross_profit_after_ad_spend": round(gp, 2),
                    "search_impression_share": None if x["is"] is None else ("< 10%" if abs(x["is"] - IS_SENTINEL) < 1e-9 else round(x["is"], 4)),
                    "lost_is_rank": None if x["rank"] is None else round(x["rank"], 4),
                    "lost_is_budget": None if x["budget"] is None else round(x["budget"], 4)}
        summary["account"] = {"gross_margin": a.margin,
                              "months": [acct_row(month_label(m), x) for m, x in acct["months"]],
                              "totals": [acct_row(v, acct["totals"][v]) for v in VIEWS]}
    if sv:
        summary["search_volume"] = {"keywords": sv["keywords"], "market": sv["market"], "complete_through": month_label(sv["complete"]),
                                    "comparisons": [{"name": c["name"], "prior": c["prior"], "current": c["current"],
                                                     "rows": [{"metric": r[0], "prior": None if r[1] is None else round(r[1]),
                                                               "current": None if r[2] is None else round(r[2]),
                                                               "change": None if r[3] is None else round(r[3], 3)} for r in c["rows"]]}
                                                    for c in sv["comparisons"]],
                                    "monthly_total_searches": {month_label(m): sv["total"](m) for m in sv["months"] if sv["total"](m) is not None}}
    fam_items, fam_rows = [], []
    if products:
        for p in products:
            p["roas"] = safe_div(p["val"], p["cost"])
            p["bucket"] = bucket(p["cost"], p["roas"], a.cost, a.roas)
        counts = defaultdict(int)
        bcost = defaultdict(float)
        for p in products:
            counts[p["bucket"]] += 1
            bcost[p["bucket"]] += p["cost"]
        facts.append(("Products listed", len(products), "int"))
        facts.append(("Profitable / Costly / Low spend / Zombies", " / ".join("{:,}".format(counts[b]) for b in BUCKETS), None))
        def brief(p):
            return {"id": p["id"], "title": p["title"], "cost": round(p["cost"], 2), "conv_value": round(p["val"], 2),
                    "roas": round(p["roas"], 2), "clicks": int(p["clicks"]), "impressions": int(p["impr"])}
        summary["products"] = {"count": len(products), "thresholds": {"roas": a.roas, "cost": a.cost},
                               "buckets": {b: {"products": counts[b], "cost": round(bcost[b], 2)} for b in BUCKETS},
                               "top_costly_by_cost": [brief(p) for p in products if p["bucket"] == "Costly"][:8],
                               "top_profitable_by_cost": [brief(p) for p in products if p["bucket"] == "Profitable"][:8],
                               "low_spend_above_roas_target": [brief(p) for p in sorted((p for p in products if p["bucket"] == "Low spend" and p["roas"] >= a.roas),
                                                                                       key=lambda p: -p["roas"])][:8],
                               "break_even_roas": round(safe_div(1, a.margin), 2) if a.margin else None,
                               "costly_below_break_even": sum(1 for p in products if p["bucket"] == "Costly" and a.margin and p["roas"] < 1 / a.margin)}
        summary["campaigns"] = [{"name": c["name"], "type": TYPE_LABEL.get(c["type"], c["type"]), "cost": round(c["total"]["cost"], 2),
                                 "conv_value": round(c["total"]["val"], 2), "roas": round(safe_div(c["total"]["val"], c["total"]["cost"]), 2)}
                                for c in camps[:15]]
        mapping = read_families(a.run, products)
        if mapping is None:
            rows, _ = suggest_families(products)
            mapping = {pkey(r["product_id"]): r["family"] for r in rows}
            warnings.append("No product-families.csv, so families were suggested automatically. Run the families command to review them.")
        fams = OrderedDict()
        unmapped = 0
        for p in products:
            fam = mapping.get(pkey(p["id"]))
            if not fam:
                fam = p["title"]
                unmapped += 1
            x = fams.setdefault(fam, {"id": fam, "title": fam, "count": 0, "feeds": set(), "statuses": set(), "impr": 0.0,
                                      "clicks": 0.0, "cost": 0.0, "conv": 0.0, "val": 0.0})
            x["count"] += 1
            for k in ("impr", "clicks", "cost", "conv", "val"):
                x[k] += p[k]
            fam_rows.append({"family": fam, "id": p["id"], "title": p["title"], "cost": p["cost"]})
        if unmapped:
            warnings.append("%d products weren't in product-families.csv, so each is its own family." % unmapped)
        for x in fams.values():
            x["feeds"], x["statuses"] = "", ""
            fam_items.append(x)
        fam_items.sort(key=lambda x: (-x["cost"], x["id"]))
        fam_rows.sort(key=lambda r: (r["family"].lower(), -r["cost"]))
        fcounts = defaultdict(int)
        for x in fam_items:
            fcounts[bucket(x["cost"], safe_div(x["val"], x["cost"]), a.family_cost, a.family_roas)] += 1
        summary["families"] = {"count": len(fam_items), "thresholds": {"roas": a.family_roas, "cost": a.family_cost},
                               "buckets": {b: fcounts[b] for b in BUCKETS}}
    if have_gap:
        miss = sum(1 for g in gaps if g["issue"] == "Missing keyword")
        facts.append(("Keyword gaps (converting PMax searches)", "{:,} ({:,} missing, {:,} not eligible)".format(len(gaps), miss, len(gaps) - miss), None))
        facts.append(("Conversions those searches brought in", sum(g["conv"] for g in gaps), "dec"))
        summary["keyword_gaps"] = {"total": len(gaps), "missing": miss, "not_eligible": len(gaps) - miss,
                                   "conversions": round(sum(g["conv"] for g in gaps), 2),
                                   "top": [{"term": g["term"], "issue": g["issue"], "conversions": round(g["conv"], 2)} for g in gaps[:10]]}

    tabs_built = []
    # Order: Start Here, Account, Search Volume, Channel Split, Campaign, Assets, Products, Product Families, Mapping, Keyword Gap
    if acct:
        tab_account(bk, acct)
        tabs_built.append("Account")
    else:
        warnings.append("No account_monthly data, so there's no Account tab.")
    if sv:
        tab_search_volume(bk, sv)
        tabs_built.append("Search Volume")
    tab_channel_split(bk, camps, meta)
    tabs_built.append("Channel Split")
    tab_campaign(bk, camps, meta)
    tabs_built.append("Campaign")
    if assets:
        tab_assets(bk, assets, meta)
        tabs_built.append("Assets")
    if products:
        product_tab(bk, "Products", "Product Data", TABS["products"], products, meta, a.roas, a.cost, "Product ID", False)
        tabs_built.append("Products")
        product_tab(bk, "Product Families", "Family Data", TABS["families"], fam_items, meta, a.family_roas, a.family_cost,
                    "Product family", True)
        tab_mapping(bk, fam_rows, meta)
        tabs_built.append("Product Families")
    if have_gap:
        tab_keyword_gap(bk, gaps, meta)
        tabs_built.append("Keyword Gap")
    start_ws = tab_start(bk, facts, tabs_built, badge)
    bk.wb.sheets.remove(start_ws)
    bk.wb.sheets.insert(0, start_ws)
    # Hidden tabs after the visible ones
    bk.wb.sheets.sort(key=lambda w: (w.hidden,))
    slug = re.sub(r"[^a-z0-9]+", "-", store.lower()).strip("-") or "account"
    path = a.out or os.path.join(a.run, "%s-google-ads-audit.xlsx" % slug)
    bk.wb.save(path)
    summary["tabs"] = ["Start Here"] + [t for x in tabs_built for t in ([x, "Product Mapping"] if x == "Product Families" else [x])]
    summary["file"] = os.path.abspath(path)
    summary["warnings"] = warnings
    with open(os.path.join(a.run, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    out(summary)


def cmd_script(a):
    src = open(os.path.join(HERE, "export-data.js"), encoding="utf-8").read()
    for k, v in (("START_DATE", a.date_from), ("END_DATE", a.date_to), ("CUSTOMER_ID", a.customer_id or "")):
        if v and k != "CUSTOMER_ID" and not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            fail("--from and --to must be YYYY-MM-DD.")
        src, n = re.subn(r"(%s: )'[^']*'" % k, lambda m: "%s'%s'" % (m.group(1), v or ""), src, count=1)
        if n != 1:
            fail("Couldn't set %s in export-data.js." % k)
    path = a.out or "google-ads-audit-export.js"
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    out({"saved": os.path.abspath(path), "date_from": a.date_from, "date_to": a.date_to,
         "customer_id": a.customer_id or "(run inside the account itself)"})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("script")
    s.add_argument("--from", dest="date_from", required=True)
    s.add_argument("--to", dest="date_to", required=True)
    s.add_argument("--customer-id")
    s.add_argument("--out")
    s = sub.add_parser("load")
    s.add_argument("source")
    s.add_argument("--run", required=True)
    s.add_argument("--account-name")
    s.add_argument("--customer-id")
    s.add_argument("--currency")
    s.add_argument("--from", dest="date_from")
    s.add_argument("--to", dest="date_to")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("families")
    s.add_argument("--run", required=True)
    s.add_argument("--write", action="store_true")
    s = sub.add_parser("planner")
    s.add_argument("file")
    s.add_argument("--run", required=True)
    s.add_argument("--market")
    s.add_argument("--language")
    s = sub.add_parser("build")
    s.add_argument("--run", required=True)
    s.add_argument("--store")
    s.add_argument("--domain")
    s.add_argument("--margin", type=float, default=0.5)
    s.add_argument("--roas", type=float, default=4.0)
    s.add_argument("--cost", type=float, default=50.0)
    s.add_argument("--family-roas", type=float)
    s.add_argument("--family-cost", type=float)
    s.add_argument("--currency-symbol")
    s.add_argument("--out")
    a = p.parse_args()
    if not a.cmd:
        p.print_help()
        sys.exit(1)
    if a.cmd == "build":
        if a.family_roas is None:
            a.family_roas = a.roas
        if a.family_cost is None:
            a.family_cost = a.cost
        if a.margin > 1:
            a.margin = a.margin / 100.0
        if a.roas > 50:
            a.roas = a.roas / 100.0
            a.family_roas = a.family_roas / 100.0 if a.family_roas > 50 else a.family_roas
    {"script": cmd_script, "load": cmd_load, "families": cmd_families, "planner": cmd_planner, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    main()
