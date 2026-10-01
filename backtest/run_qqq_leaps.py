#!/usr/bin/env python3
"""Hold QQQ; on each weekly Cipher B green dot, buy LEAPS calls with a margin
loan of 25% of equity and hold them to expiry (no sell signal).

At expiry the calls pay intrinsic value; the loan plus interest is repaid and
the rest goes back into QQQ. Calls bought at the next week's open after the
signal. One position at a time unless STACK is set (then every green dot adds
a new position, even while others are open).

Pricing (no historical options data): Black-Scholes, no dividends.
IV = 50% x (26-week realized vol x 1.1) + 50% x 22% long-run level, floor
12%. 2% of premium lost to the spread when buying.

Usage: python3 backtest/run_qqq_leaps.py WEEKLY_PRICES_DIR [SYMBOL]
"""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from run_qqq_leverage import bs_call, run_weights, stats, weekly_rate  # noqa: E402
from run_weekly_addon import WARMUP, load_weekly  # noqa: E402

LEVER = 0.25
SPREAD = 0.02
LONG_RUN_IV = 0.22


def implied_vol(wk):
    rv = np.log(wk.close).diff().rolling(26).std() * math.sqrt(52)
    iv = 0.5 * rv.fillna(LONG_RUN_IV) * 1.1 + 0.5 * LONG_RUN_IV
    return np.maximum(iv.to_numpy(), 0.12)


def green_dots(wk):
    buy, _ = ind.cipher_b_signals(wk)
    return [t for t in range(WARMUP, len(wk) - 1) if buy.iloc[t]]


def run(wk, entries, years, moneyness, stack=False):
    """entries: signal bars; the trade fills at the next bar's open."""
    o, c = wk.open.to_numpy(), wk.close.to_numpy()
    iv, rate = implied_vol(wk), weekly_rate(wk.index)
    n_weeks = int(round(years * 52))
    shares = 1.0 / o[WARMUP + 1]
    pos, trades, eq = [], [], []  # pos: dict(n, strike, expiry_bar, debt)
    entry_set = {t + 1 for t in entries}
    for t in range(WARMUP + 1, len(wk)):
        for p in [p for p in pos if p["expiry"] == t]:     # expire at open
            payoff = p["n"] * max(o[t] - p["strike"], 0.0)
            shares += (payoff - p["debt"]) / o[t]
            trades.append({"bought": wk.index[p["start"]].date(),
                           "expired": wk.index[t].date(),
                           "qqq_move": o[t] / o[p["start"]] - 1,
                           "calls_return": payoff / p["cost"] - 1,
                           "net_after_loan": payoff - p["debt"],
                           "equity_at_buy": p["equity"]})
            pos.remove(p)
        if t in entry_set and (stack or not pos):          # buy at open
            equity = shares * o[t] + sum(
                p["n"] * bs_call(o[t], p["strike"], (p["expiry"] - t) / 52,
                                 rate[t] * 52, iv[t - 1]) - p["debt"]
                for p in pos)
            loan = LEVER * equity
            strike = o[t] * moneyness
            prem = bs_call(o[t], strike, years, rate[t] * 52, iv[t - 1])
            pos.append({"n": loan / (prem * (1 + SPREAD)), "strike": strike,
                        "expiry": t + n_weeks, "debt": loan, "cost": loan,
                        "start": t, "equity": equity})
        for p in pos:
            p["debt"] *= 1 + rate[t]
        eq.append(shares * c[t] + sum(
            p["n"] * bs_call(c[t], p["strike"], (p["expiry"] - t) / 52,
                             rate[t] * 52, iv[t]) - p["debt"] for p in pos))
    for p in pos:  # still open at the end: mark to model
        trades.append({"bought": wk.index[p["start"]].date(),
                       "expired": "open", "qqq_move": c[-1] / o[p["start"]] - 1,
                       "calls_return": np.nan, "net_after_loan": np.nan,
                       "equity_at_buy": p["equity"]})
    return pd.Series(eq, index=wk.index[WARMUP + 1:]), pd.DataFrame(trades)


def main():
    src = sys.argv[1]
    sym = sys.argv[2] if len(sys.argv) > 2 else "QQQ"
    wk = load_weekly(os.path.join(src, f"{sym}.csv"))
    dots = green_dots(wk)
    print(f"{sym} weekly {wk.index[WARMUP + 1].date()} .. "
          f"{wk.index[-1].date()}; green dots: "
          + ", ".join(str((wk.index[t] - pd.Timedelta(days=4)).date())
                      for t in dots))
    n = len(wk)
    rows = {"buy_hold": stats((1 + run_weights(wk, np.zeros(n))).cumprod()),
            "constant_125_margin": stats(
                (1 + run_weights(wk, np.full(n, LEVER))).cumprod())}
    rng = np.random.default_rng(0)
    details = {}
    for years in (1, 2):
        for mny, label in ((1.0, "ATM"), (0.9, "10%ITM")):
            for stack in (False, True):
                name = f"leaps_{years}y_{label}" + ("_stack" if stack else "")
                eq, tr = run(wk, dots, years, mny, stack)
                rows[name] = stats(eq)
                details[name] = tr
                if not stack:
                    rnd = []
                    for _ in range(300):
                        k = len(dots)
                        fake = sorted(rng.choice(
                            np.arange(WARMUP, n - 1), size=k, replace=False))
                        rnd.append(stats(run(wk, fake, years, mny)[0]))
                    rnd = pd.DataFrame(rnd)
                    rows[name + " (random, median)"] = rnd.median().to_dict()
                    rows[name]["beats_random"] = (rnd.cagr <
                                                  rows[name]["cagr"]).mean()
    out = pd.DataFrame(rows).T
    pd.set_option("display.width", 220)
    print(out.round(3).to_string())
    for name in ("leaps_2y_ATM", "leaps_2y_ATM_stack", "leaps_1y_ATM"):
        print(f"\n{name} trades:")
        print(details[name].to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    out.to_csv(f"{sym.lower()}_leaps_summary.csv")


if __name__ == "__main__":
    main()
