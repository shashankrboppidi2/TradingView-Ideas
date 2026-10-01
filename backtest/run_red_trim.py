#!/usr/bin/env python3
"""Trim on weekly Cipher B red dots, restore on green dots (or a time limit).

Start 100% invested. On a red dot, cut the position to (1 - trim) at the
next week's open; restore to 100% on the next green dot, or (if max_weeks is
set) after that many weeks, whichever comes first. A red dot while already
trimmed is ignored. Cash earns nothing (conservative).

Each variant is compared with buy-and-hold and with the same trims placed at
random weeks (same count and lengths per market; 200 shuffles), which shows
whether the red-dot timing matters or any trimming would do the same.

Usage: python3 backtest/run_red_trim.py WEEKLY_PRICES_DIR
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from engine import returns_weighted  # noqa: E402
from run_weekly_addon import (COSTS, DEFAULT_COST, MIN_WEEKS, PERIODS,  # noqa: E402
                              WARMUP, load_weekly, stats)

INDEX_LIKE = {"QQQ", "SPY", "IWM", "XLE", "GLD", "TLT", "USO", "EURUSD",
              "BTC", "ETH"}
VARIANTS = [(1 / 3, None), (1 / 3, 26), (0.5, None), (0.5, 26),
            (1.0, None), (1.0, 26)]


def name_of(trim, max_weeks):
    t = {1 / 3: "trim_third", 0.5: "trim_half", 1.0: "exit_all"}[trim]
    return t + ("_green_or_26wk" if max_weeks else "_green_only")


def trim_windows(buy, sell, max_weeks):
    """(start, end) bars of trimmed periods, in signal-bar terms."""
    wins, start = [], None
    for t in range(WARMUP, len(buy)):
        if start is None and sell[t]:
            start = t
        elif start is not None and (buy[t] or (max_weeks and
                                               t - start >= max_weeks)):
            wins.append((start, t))
            start = None
    if start is not None:
        wins.append((start, len(buy)))
    return wins


def weights_from(wins, n, trim):
    w = np.ones(n)
    w[:WARMUP] = 0
    for a, b in wins:
        w[a:b] = 1 - trim
    return w


def main():
    src = sys.argv[1]
    rng = np.random.default_rng(7)
    port = {}      # variant -> {market: weekly returns}
    rand_port = {}  # variant -> list of {market: returns} per shuffle
    shuffles = 200
    for path in sorted(glob.glob(os.path.join(src, "*.csv"))):
        name = os.path.basename(path)[:-4]
        wk = load_weekly(path)
        n = len(wk)
        if n < WARMUP + MIN_WEEKS:
            continue
        cost = COSTS.get(name, DEFAULT_COST)
        buy, sell = (s.to_numpy() for s in ind.cipher_b_signals(wk))
        bh = np.ones(n)
        bh[:WARMUP] = 0
        port.setdefault("buy_hold", {})[name] = returns_weighted(
            wk, pd.Series(bh, index=wk.index), cost).iloc[WARMUP + 1:]
        for trim, mw in VARIANTS:
            v = name_of(trim, mw)
            wins = trim_windows(buy, sell, mw)
            w = weights_from(wins, n, trim)
            port.setdefault(v, {})[name] = returns_weighted(
                wk, pd.Series(w, index=wk.index), cost).iloc[WARMUP + 1:]
            lengths = [b - a for a, b in wins]
            sims = rand_port.setdefault(v, [{} for _ in range(shuffles)])
            for s in range(shuffles):
                rw = np.ones(n)
                rw[:WARMUP] = 0
                for L in lengths:
                    a = rng.integers(WARMUP, max(WARMUP + 1, n - L))
                    rw[a:a + L] = 1 - trim
                sims[s][name] = returns_weighted(
                    wk, pd.Series(rw, index=wk.index), cost).iloc[WARMUP + 1:]

    def summarise(by_mkt, keep):
        r = pd.DataFrame({k: v for k, v in by_mkt.items() if keep(k)})
        return r.sort_index().mean(axis=1)

    pd.set_option("display.width", 220)
    for label, keep in (("individual stocks (equal weight)",
                         lambda k: k not in INDEX_LIKE),
                        ("QQQ", lambda k: k == "QQQ"),
                        ("SPY", lambda k: k == "SPY")):
        rows = {}
        for v, by_mkt in port.items():
            pr = summarise(by_mkt, keep)
            row = stats(pr)
            for per, a, b in PERIODS:
                row[f"sharpe_{per}"] = stats(pr[a:b])["sharpe"]
            if v in rand_port:
                rs = pd.DataFrame([stats(summarise(sim, keep))
                                   for sim in rand_port[v]])
                row["random_sharpe_median"] = rs.sharpe.median()
                row["random_maxdd_median"] = rs.max_dd.median()
                row["beats_random_sharpe"] = (rs.sharpe < row["sharpe"]).mean()
            rows[v] = row
        print(f"\n== {label} ==")
        print(pd.DataFrame(rows).T.round(3).to_string())


if __name__ == "__main__":
    main()
