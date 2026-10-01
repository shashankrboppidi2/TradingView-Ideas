#!/usr/bin/env python3
"""Does a Cipher B dot predict the next weeks' returns? (No exits, no
leverage, no options: just what price did after each signal.)

For every signal, the forward return from the next bar's open to the close
H bars later is compared with that market's average H-bar forward return
over its whole history ("excess"). Signals cluster in market-wide selloffs,
so significance is measured on calendar-month clusters: excess returns are
averaged within each month and the t-statistic is taken across months.

Usage: python3 backtest/event_study.py PRICES_DIR {weekly|daily}
"""
import glob
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from run_weekly_addon import WARMUP, load_weekly  # noqa: E402
from engine import load  # noqa: E402

HORIZONS = {"weekly": [4, 13, 26, 52], "daily": [5, 20, 60, 120]}


def events(df, horizons):
    buy, sell = ind.cipher_b_signals(df)
    wt1, wt2 = ind.wavetrend(df)
    up = (wt1 > wt2) & (wt1.shift(1) <= wt2.shift(1))
    down = (wt1 < wt2) & (wt1.shift(1) >= wt2.shift(1))
    o, c = df.open.to_numpy(), df.close.to_numpy()
    n = len(df)
    base = {h: np.array([c[t + h] / o[t + 1] - 1
                         for t in range(WARMUP, n - h - 1)])
            for h in horizons}
    mean = {h: base[h].mean() for h in horizons}
    rows = []
    kinds = {"green_dot": buy, "red_dot": sell,
             "any_cross_up": up, "any_cross_down": down}
    for kind, sig in kinds.items():
        for t in np.flatnonzero(sig.to_numpy()):
            if t < WARMUP:
                continue
            row = {"kind": kind, "date": df.index[t]}
            for h in horizons:
                if t + h + 1 < n:
                    fwd = c[t + h] / o[t + 1] - 1
                    row[f"fwd_{h}"] = fwd
                    row[f"ex_{h}"] = fwd - mean[h]
            rows.append(row)
    return rows, {h: (mean[h], (base[h] > 0).mean()) for h in horizons}


def clustered_t(df, col):
    m = df.dropna(subset=[col]).groupby(df.date.dt.to_period("M"))[col].mean()
    if len(m) < 3 or m.std() == 0:
        return np.nan, len(m)
    return m.mean() / (m.std() / math.sqrt(len(m))), len(m)


def main():
    src, mode = sys.argv[1], sys.argv[2]
    horizons = HORIZONS[mode]
    allrows, base_hit = [], {h: [] for h in horizons}
    for path in sorted(glob.glob(os.path.join(src, "*.csv"))):
        name = os.path.basename(path)[:-4]
        df = (load_weekly(path) if mode == "weekly"
              else load(path, drop_after="2026-09-30"))
        if len(df) < WARMUP + 156:
            continue
        rows, base = events(df, horizons)
        for r in rows:
            r["market"] = name
        allrows += rows
        for h in horizons:
            base_hit[h].append(base[h][1])
    ev = pd.DataFrame(allrows)
    unit = "wk" if mode == "weekly" else "d"
    print(f"{mode}: {ev.market.nunique()} markets")
    print("baseline share of positive forward returns (avg over markets): "
          + ", ".join(f"{h}{unit} {np.mean(base_hit[h]):.0%}"
                      for h in horizons))
    out = []
    for kind, g in ev.groupby("kind", sort=False):
        for h in horizons:
            col = f"ex_{h}"
            t, months = clustered_t(g, col)
            gg = g.dropna(subset=[col])
            out.append({"signal": kind, "horizon": f"{h}{unit}",
                        "events": len(gg), "months": months,
                        "avg_fwd": gg[f"fwd_{h}"].mean(),
                        "avg_excess": gg[col].mean(),
                        "median_excess": gg[col].median(),
                        "hit_rate": (gg[f"fwd_{h}"] > 0).mean(),
                        "t_clustered": t})
    res = pd.DataFrame(out)
    pd.set_option("display.width", 200)
    print(res.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    res.to_csv(f"event_study_{mode}.csv", index=False)


if __name__ == "__main__":
    main()
