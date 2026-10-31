"""Pulls public RSS feeds + currency rates and writes news.json.
Edit FEEDS to add or remove sources. Uses only the Python standard library."""
import json, re, time, html, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime

FEEDS = [
    ("The Daily Star", "bangladesh", "https://www.thedailystar.net/business/rss.xml"),
    ("The Business Standard", "bangladesh", "https://www.tbsnews.net/rss.xml"),
    ("The Financial Express", "bangladesh", "https://thefinancialexpress.com.bd/feed"),
    ("BBC Business", "international", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Al Jazeera", "international", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Forbes", "international", "https://www.forbes.com/business/feed/"),
    ("The Guardian Business", "international", "https://www.theguardian.com/uk/business/rss"),
]
UA = {"User-Agent": "Mozilla/5.0 (BusinessWireBD feed reader)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def strip_ns(tag):
    return tag.split("}")[-1]


def child(el, *names):
    for c in el:
        if strip_ns(c.tag) in names:
            return c
    return None


def parse_date(text):
    text = (text or "").strip()
    if not text:
        return 0
    try:
        return int(parse_date_email(text))
    except Exception:
        pass
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return 0


def parse_date_email(text):
    return parsedate_to_datetime(text).timestamp() * 1000


def classify(title, base):
    if re.search(r"bank|loan|NPL|interest rate|monetary|lender|deposit", title, re.I):
        return "banking"
    if re.search(r"startup|fintech|venture|funding round", title, re.I):
        return "startups"
    if base == "international" and re.search(r"inflation|GDP|economy|budget|tax|trade|tariff", title, re.I):
        return "economy"
    return base


def read_feed(name, base, url):
    root = ET.fromstring(get(url))
    out = []
    for el in root.iter():
        if strip_ns(el.tag) not in ("item", "entry"):
            continue
        t = child(el, "title")
        title = clean(t.text if t is not None else "")
        l = child(el, "link")
        link = ""
        if l is not None:
            link = (l.text or "").strip() or l.get("href", "")
        d = child(el, "pubDate", "published", "updated")
        s = child(el, "description", "summary")
        if title and link:
            out.append({
                "t": title, "l": link, "src": name,
                "s": clean(s.text if s is not None else "")[:150],
                "c": classify(title, base),
                "d": parse_date(d.text if d is not None else ""),
            })
        if len(out) >= 15:
            break
    return out


def main():
    items, status = [], []
    for name, base, url in FEEDS:
        try:
            got = read_feed(name, base, url)
            items += got
            status.append({"n": name, "ok": len(got) > 0})
        except Exception as e:
            print("FAILED", name, e)
            status.append({"n": name, "ok": False})
    seen, uniq = set(), []
    for i in sorted(items, key=lambda x: x["d"], reverse=True):
        if i["l"] not in seen:
            seen.add(i["l"])
            uniq.append(i)

    rates = {}
    try:
        j = json.loads(get("https://open.er-api.com/v6/latest/USD"))
        bdt = j["rates"]["BDT"]
        for k in ["USD", "EUR", "GBP", "INR", "SAR", "AED", "JPY"]:
            rates[k] = bdt / j["rates"][k]
    except Exception as e:
        print("RATES FAILED", e)

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump({"items": uniq[:90], "status": status, "rates": rates,
                   "updated": int(time.time() * 1000)}, f, ensure_ascii=False)
    print("OK", len(uniq), "items;", sum(s["ok"] for s in status), "of", len(status), "sources")


main()
