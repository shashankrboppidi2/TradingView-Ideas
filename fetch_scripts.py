#!/usr/bin/env python3
"""Rank TradingView's public (open-source) scripts by boosts.

TradingView's "Most popular" sort runs client-side, so this approximates an
all-time ranking by running many script searches (indicator names, concepts,
well-known authors), merging the results and sorting by boost count.

Usage:
    python3 fetch_scripts.py                       # -> scripts_ranked.csv
    python3 fetch_scripts.py --pages 1 -o out.csv  # quicker, shallower
"""
import argparse
import csv
import sys
import time
import urllib.error
import urllib.parse

from fetch_ideas import find_key, get, init_blobs

SEARCH = "https://www.tradingview.com/scripts/search/{q}/"
QUERIES = """vumanchu|cipher|wavetrend|squeeze momentum|lazybear|supertrend|ut bot|
range filter|chandelier exit|ssl channel|halftrend|hull suite|nadaraya watson|
lorentzian|machine learning|smart money concepts|order blocks|fair value gap|
support resistance|pivot points|ichimoku|macd|rsi divergence|stochastic rsi|
bollinger bands|keltner|atr trailing stop|volume profile|vwap|market structure|
trendlines with breaks|zigzag|heikin ashi|qqe|adx|aroon|parabolic sar|donchian|
turtle|ema ribbon|moving average|kalman|fibonacci|elliott wave|divergence|
money flow|obv|cumulative volume delta|liquidity|sessions|ttm squeeze|
coral trend|ehlers|schaff trend cycle|trend magic|alphatrend|follow line|
optimized trend tracker|gaussian channel|pi cycle|logarithmic regression|
williams vix fix|cm_|chrismoody|kivancozbilgic|luxalgo|everget|jdehorty|
bigbeluga|chartprime|algoalpha|zeiierman|donovanwall|quantnomad|
buy sell signals|trend following|mean reversion|momentum|breakout|
regression channel|linear regression|super trend ai|mtf|relative strength|rsi|
stochastic|cci|wave trend oscillator|market cipher|swing|scalping|
trend indicator|volatility|atr|ema cross|golden cross|200 ma|weekly|
bitcoin cycle|rainbow|hash ribbons|mvrv|bull market support band|chop zone|
vortex|tsi|kst|ultimate oscillator|fisher transform|stc|mcginley|alma|jma|t3|
tilson|zero lag|hma|dema|tema|kama|frama|vidya"""
QUERIES = [q.strip() for q in QUERIES.split("|") if q.strip()]


def search_page(query, page):
    url = SEARCH.format(q=urllib.parse.quote(query))
    if page > 1:
        url += f"page-{page}/"
    for blob in init_blobs(get(url)):
        for items in find_key(blob, "items"):
            if (isinstance(items, list) and items
                    and isinstance(items[0], dict)
                    and "likes_count" in items[0]):
                return items
    return []


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", type=int, default=3,
                    help="search result pages per query")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("-o", "--out", default="scripts_ranked.csv")
    args = ap.parse_args()

    scripts = {}
    for query in QUERIES:
        for page in range(1, args.pages + 1):
            try:
                items = search_page(query, page)
            except urllib.error.HTTPError:
                break
            if not items:
                break
            for s in items:
                scripts[s["id"]] = s
            time.sleep(args.delay)
        print(f"{query}: {len(scripts)} unique", file=sys.stderr)

    ranked = sorted(scripts.values(), key=lambda s: -s["likes_count"])
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "boosts", "comments", "name", "author", "type",
                    "published", "url"])
        for i, s in enumerate(ranked, 1):
            w.writerow([i, s["likes_count"], s["comments_count"], s["name"],
                        (s.get("user") or {}).get("username"),
                        s.get("script_type"), s["created_at"][:10],
                        s["chart_url"]])
    print(f"wrote {len(ranked)} scripts to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
