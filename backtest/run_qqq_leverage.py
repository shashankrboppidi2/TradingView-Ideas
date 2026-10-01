#!/usr/bin/env python3
"""Buy-and-hold QQQ, adding 25% leverage on weekly Cipher B signals.

Lever up:   weekly Cipher B green dot (WT cross up with WT2 <= -53).
Lever down: weekly red dot at the overbought line (WT cross down with
            WT2 >= +53) while Stoch RSI %K >= 80.
Signals fire on the week's close; trades fill at the next week's open.

Variants
  buy_hold         100% QQQ
  constant_125     125% QQQ all the time (margin)
  signal_margin    100%, or 125% via margin while the signal is active
  signal_calls     100% QQQ, plus ~1-year ATM calls bought with a margin
                   loan of 25% of equity while the signal is active
  random_margin    like signal_margin, but entries on random weeks with the
                   same number of trades and the same holding lengths
                   (median of 1000 shuffles)

Margin interest: approximate annual Fed funds average + 1.5%.
Calls: Black-Scholes; IV = 26-week realized vol x 1.1 (floor 12%); 2% of
premium lost to the spread on each buy/sell; rolled at 26 weeks to expiry.

Usage: python3 backtest/run_qqq_leverage.py WEEKLY_PRICES_DIR [SYMBOL]
"""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from run_weekly_addon import WARMUP, load_weekly  # noqa: E402

LEVER = 0.25
COST = 0.0005          # per side on QQQ trades
SPREAD = 0.02          # fraction of option premium lost per side
CALL_YEARS, ROLL_AT = 1.0, 0.5
# Approximate annual average effective Fed funds rate (%), from memory.
FED_FUNDS = {1999: 5.0, 2000: 6.2, 2001: 3.9, 2002: 1.7, 2003: 1.1,
             2004: 1.35, 2005: 3.2, 2006: 5.0, 2007: 5.0, 2008: 1.9,
             2009: 0.15, 2010: 0.15, 2011: 0.1, 2012: 0.15, 2013: 0.1,
             2014: 0.1, 2015: 0.15, 2016: 0.4, 2017: 1.0, 2018: 1.8,
             2019: 2.2, 2020: 0.4, 2021: 0.1, 2022: 1.7, 2023: 5.0,
             2024: 5.1, 2025: 4.2, 2026: 3.8}


def signal_windows(wk):
    """List of (entry_bar, exit_bar) where bars are the fill (next) weeks."""
    wt1, wt2 = ind.wavetrend(wk)
    k = ind.stoch_rsi_k(wk.close)
    up = (wt1 > wt2) & (wt1.shift(1) <= wt2.shift(1))
    down = (wt1 < wt2) & (wt1.shift(1) >= wt2.shift(1))
    green = (up & (wt2 <= -53)).to_numpy()
    red_peak = (down & (wt2 >= 53) & (k >= 80)).to_numpy()
    wins, entry = [], None
    for t in range(WARMUP, len(wk) - 1):
        if entry is None and green[t]:
            entry = t + 1
        elif entry is not None and red_peak[t]:
            wins.append((entry, t + 1))
            entry = None
    if entry is not None:
        wins.append((entry, len(wk)))  # still open at the end
    return wins


def weekly_rate(dates):
    return np.array([(FED_FUNDS.get(d.year, 3.0) + 1.5) / 100 / 52
                     for d in dates])


def run_weights(wk, lev):
    """Weekly returns for a leverage path; lev[t] = extra exposure in week t
    (traded at week t's open). Margin interest on the borrowed part."""
    o, c = wk.open.to_numpy(), wk.close.to_numpy()
    w = 1 + lev
    rate = weekly_rate(wk.index)
    r = np.zeros(len(wk))
    for t in range(WARMUP + 1, len(wk)):
        r[t] = (w[t - 1] * (o[t] / c[t - 1] - 1) + w[t] * (c[t] / o[t] - 1)
                - COST * abs(w[t] - w[t - 1]) - lev[t] * rate[t])
    return pd.Series(r[WARMUP + 1:], index=wk.index[WARMUP + 1:])


def bs_call(s, k, t, r, vol):
    if t <= 0:
        return max(s - k, 0.0)
    d1 = (math.log(s / k) + (r + vol * vol / 2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    cdf = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))  # noqa: E731
    return s * cdf(d1) - k * math.exp(-r * t) * cdf(d2)


def run_calls(wk, wins):
    """Equity path for 100% QQQ plus financed calls during signal windows."""
    o, c = wk.open.to_numpy(), wk.close.to_numpy()
    rv = np.log(wk.close).diff().rolling(26).std().to_numpy() * math.sqrt(52)
    iv = np.maximum(np.nan_to_num(rv, nan=0.2) * 1.1, 0.12)
    rate = weekly_rate(wk.index)
    starts = {a: b for a, b in wins}
    shares = 1.0 / o[WARMUP + 1]   # 100% QQQ with $1 at the first open
    debt, n_calls, strike, expiry = 0.0, 0.0, 0.0, 0.0
    exit_at, trades, eq = None, [], []
    entry_val = None
    for t in range(WARMUP + 1, len(wk)):
        yrs = t / 52.18
        rr = rate[t] * 52
        if n_calls and exit_at == t:                       # sell at open
            proceeds = n_calls * bs_call(o[t], strike, expiry - yrs, rr,
                                         iv[t - 1]) * (1 - SPREAD)
            shares += (proceeds - debt) / o[t] * (1 - COST)
            trades.append((wk.index[t].date(), proceeds / entry_val - 1))
            n_calls = debt = 0.0
        if t in starts and not n_calls:                    # buy at open
            exit_at = starts[t]
            debt = LEVER * shares * o[t]
            strike, expiry = o[t], yrs + CALL_YEARS
            prem = bs_call(o[t], strike, CALL_YEARS, rr, iv[t - 1])
            n_calls = debt / (prem * (1 + SPREAD))
            entry_val = debt
        if n_calls and expiry - yrs <= ROLL_AT:            # roll at open
            val = n_calls * bs_call(o[t], strike, expiry - yrs, rr,
                                    iv[t - 1]) * (1 - SPREAD)
            strike, expiry = o[t], yrs + CALL_YEARS
            prem = bs_call(o[t], strike, CALL_YEARS, rr, iv[t - 1])
            n_calls = val / (prem * (1 + SPREAD))
        debt *= 1 + rate[t]
        calls_val = (n_calls * bs_call(c[t], strike, expiry - yrs, rr, iv[t])
                     if n_calls else 0.0)
        eq.append(shares * c[t] + calls_val - debt)
    return pd.Series(eq, index=wk.index[WARMUP + 1:]), trades


def stats(eq):
    r = eq.pct_change().dropna()
    years = len(r) / 52.18
    return {"cagr": (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1,
            "sharpe": r.mean() / r.std() * math.sqrt(52.18),
            "max_dd": (eq / eq.cummax() - 1).min(),
            "final_x": eq.iloc[-1] / eq.iloc[0]}


def main():
    src = sys.argv[1]
    sym = sys.argv[2] if len(sys.argv) > 2 else "QQQ"
    wk = load_weekly(os.path.join(src, f"{sym}.csv"))
    wins = signal_windows(wk)
    n = len(wk)

    lev = np.zeros(n)
    for a, b in wins:
        lev[a:b] = LEVER
    curves = {
        "buy_hold": (1 + run_weights(wk, np.zeros(n))).cumprod(),
        "constant_125": (1 + run_weights(wk, np.full(n, LEVER))).cumprod(),
        "signal_margin": (1 + run_weights(wk, lev)).cumprod(),
    }
    calls_eq, call_trades = run_calls(wk, wins)
    curves["signal_calls"] = calls_eq

    # Random-timing control: same number of windows and lengths.
    rng = np.random.default_rng(0)
    lengths = [b - a for a, b in wins]
    rand = []
    for _ in range(1000):
        lv = np.zeros(n)
        for L in lengths:
            a = rng.integers(WARMUP + 1, max(WARMUP + 2, n - L))
            lv[a:a + L] = LEVER
        rand.append(stats((1 + run_weights(wk, lv)).cumprod()))
    rand = pd.DataFrame(rand)

    rows = {k: stats(v) for k, v in curves.items()}
    rows["random_margin (median)"] = rand.median().to_dict()
    out = pd.DataFrame(rows).T
    pd.set_option("display.width", 200)
    print(f"{sym} weekly {wk.index[WARMUP + 1].date()} .. {wk.index[-1].date()}")
    print(out.round(3))
    sm = rows["signal_margin"]["cagr"]
    print(f"signal_margin CAGR beats {(rand.cagr < sm).mean():.0%} of "
          f"random-timing runs")
    print("\nSignal windows (fill week of entry -> exit), QQQ move, calls P&L:")
    o = wk.open.to_numpy()
    for i, (a, b) in enumerate(wins):
        end = wk.index[b].date() if b < n else "open"
        px_end = o[b] if b < n else wk.close.iloc[-1]
        cp = call_trades[i][1] if i < len(call_trades) else float("nan")
        print(f"  {wk.index[a].date()} -> {end}  ({b - a} wks)  "
              f"QQQ {px_end / o[a] - 1:+.1%}  calls {cp:+.0%}")
    out.to_csv(f"{sym.lower()}_leverage_summary.csv")
    pd.DataFrame(curves).to_csv(f"{sym.lower()}_leverage_curves.csv")


if __name__ == "__main__":
    main()
