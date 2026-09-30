#!/usr/bin/env python3
"""Fetch public ideas from https://www.tradingview.com/ideas/ into a JSONL file.

The feed pages embed their data as JSON in a
<script type="application/prs.init-data+json"> tag, so no HTML scraping is
needed. The feed exposes at most 1000 ideas (42 pages of 24).

Usage:
    python3 fetch_ideas.py                    # all feed pages -> ideas.jsonl
    python3 fetch_ideas.py --pages 3          # first 3 pages only
    python3 fetch_ideas.py --full             # also fetch each idea's full text
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://www.tradingview.com/ideas/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
INIT_DATA = re.compile(
    r'<script type="application/prs\.init-data\+json">(.*?)</script>', re.S)
DIRECTIONS = {0: "neutral", 1: "long", 2: "short"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def init_blobs(html):
    for m in INIT_DATA.finditer(html):
        yield json.loads(m.group(1))


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            yield obj[key]
        for v in obj.values():
            yield from find_key(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from find_key(v, key)


def feed_page(page):
    url = BASE if page == 1 else f"{BASE}page-{page}/"
    for blob in init_blobs(get(url)):
        for ideas in find_key(blob, "ideas"):
            if isinstance(ideas, dict) and "items" in ideas.get("data", {}):
                return ideas["data"]["items"]
    return []


def full_description(chart_url, fallback):
    """The feed truncates descriptions; the idea page has the full text."""
    best = fallback
    for blob in init_blobs(get(chart_url)):
        for d in find_key(blob, "description"):
            if isinstance(d, str) and len(d) > len(best):
                best = d
    return best


def normalize(item):
    sym = item.get("symbol") or {}
    user = item.get("user") or {}
    return {
        "id": item["id"],
        "title": item["name"],
        "url": item["chart_url"],
        "created_at": item["created_at"],
        "symbol": sym.get("name"),
        "interval": sym.get("interval"),
        "direction": DIRECTIONS.get(sym.get("direction"), sym.get("direction")),
        "author": user.get("username"),
        "likes": item.get("likes_count"),
        "comments": item.get("comments_count"),
        "is_education": item.get("is_education"),
        "is_picked": item.get("is_picked"),
        "is_video": item.get("is_video"),
        "image": (item.get("image") or {}).get("big"),
        "description": item.get("description", ""),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", type=int, default=42, help="max feed pages")
    ap.add_argument("--full", action="store_true",
                    help="fetch each idea page for its full description")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests")
    ap.add_argument("-o", "--out", default="ideas.jsonl")
    args = ap.parse_args()

    seen = set()
    with open(args.out, "w") as out:
        for page in range(1, args.pages + 1):
            try:
                items = feed_page(page)
            except urllib.error.HTTPError as e:
                print(f"page {page}: HTTP {e.code}, stopping", file=sys.stderr)
                break
            if not items:
                break
            for item in items:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                idea = normalize(item)
                if args.full:
                    time.sleep(args.delay)
                    idea["description"] = full_description(
                        idea["url"], idea["description"])
                out.write(json.dumps(idea, ensure_ascii=False) + "\n")
            print(f"page {page}: {len(items)} ideas ({len(seen)} total)",
                  file=sys.stderr)
            time.sleep(args.delay)
    print(f"wrote {len(seen)} ideas to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
