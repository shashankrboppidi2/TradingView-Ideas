#!/usr/bin/env python3
"""LEAPS on weekly green dots, rolled every 6 months while underwater.

Compares hold-to-expiry with two roll styles (see run_qqq_leaps.run):
roll down-and-out (proceeds only) and roll out at the same strike (debit
added to the margin loan). Random-week entries with the same rules give the
baseline for whether the green-dot timing matters.

Usage: python3 backtest/run_qqq_leaps_roll.py WEEKLY_PRICES_DIR [SYMBOL]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from run_qqq_leaps import green_dots, run  # noqa: E402
from run_qqq_leverage import run_weights, stats  # noqa: E402
from run_weekly_addon import WARMUP, load_weekly  # noqa: E402


def main():
    src = sys.argv[1]
    sym = sys.argv[2] if len(sys.argv) > 2 else "QQQ"
    wk = load_weekly(os.path.join(src, f"{sym}.csv"))
    dots, n = green_dots(wk), len(wk)
    rows = {"buy_hold": stats((1 + run_weights(wk, np.zeros(n))).cumprod())}
    rng = np.random.default_rng(1)
    trades = {}
    for years in (1, 2):
        for roll in (None, "down_out", "same_strike"):
            name = f"{years}y_ATM_" + (roll or "hold_to_expiry")
            eq, tr = run(wk, dots, years, 1.0, roll=roll)
            rows[name] = stats(eq)
            trades[name] = tr
            rnd = pd.DataFrame([
                stats(run(wk, sorted(rng.choice(np.arange(WARMUP, n - 1),
                                                len(dots), replace=False)),
                          years, 1.0, roll=roll)[0]) for _ in range(300)])
            rows[name]["random_median_cagr"] = rnd.cagr.median()
            rows[name]["beats_random"] = (rnd.cagr < rows[name]["cagr"]).mean()
    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).T.round(3).to_string())
    for name, tr in trades.items():
        if "hold" in name and name.startswith("1y"):
            continue
        print(f"\n{name}:")
        print(tr.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    pd.DataFrame(rows).T.to_csv(f"{sym.lower()}_leaps_roll_summary.csv")


if __name__ == "__main__":
    main()
