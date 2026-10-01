#!/usr/bin/env python3
"""Layered test: does each add-on improve VuManChu Cipher B on daily bars?

Variants (all long-only, default indicator settings, no tuning):
  buy_hold        hold from the first tradable bar
  trend_only      in the market while weekly SuperTrend(10,3) is up
  cipher          enter on Cipher B buy dot, exit on sell dot
  cipher_trend    + only enter while weekly SuperTrend is up; exit on flip
  cipher_trend_ce + exit on Chandelier Exit(22,3) instead of the sell dot
  cipher_full     + skip entries while the LazyBear squeeze is on
  cipher_trail    Cipher B entries, exit on a 3x ATR(22) trail anchored at
                  the highest close since entry (no trend filter)
  cipher_sqz      Cipher B entries/exits, skip entries while squeeze is on

Usage: python3 backtest/run_cipher_layers.py PRICES_DIR [OUT_CSV]
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from engine import load, metrics, returns_from_positions  # noqa: E402

WARMUP = 80  # bars before any variant may trade (weekly ST needs ~11 weeks)
COSTS = {"BTC": 0.001, "ETH": 0.001, "EURUSD": 0.0002}  # per side
DEFAULT_COST = 0.0005
LAST_COMPLETE_BAR = "2026-09-30"


def positions(df):
    n = len(df)
    buy, sell = ind.cipher_b_signals(df)
    wst = ind.weekly_supertrend(df)
    stop = ind.chandelier_long_stop(df)
    sqz = ind.squeeze_on(df)
    close = df.close.to_numpy()
    buy, sell = buy.to_numpy(), sell.to_numpy()
    up = (wst == 1).to_numpy()
    stop, sqz = stop.to_numpy(), sqz.to_numpy()
    atr22 = ind.atr(df, 22).to_numpy()

    out = {name: np.zeros(n) for name in
           ("buy_hold", "trend_only", "cipher", "cipher_trend",
            "cipher_trend_ce", "cipher_full", "cipher_trail", "cipher_sqz")}
    state = dict.fromkeys(out, 0)
    peak = None  # highest close since cipher_trail entry
    for t in range(WARMUP, n):
        s = state
        s["buy_hold"] = 1
        s["trend_only"] = int(up[t])

        if s["cipher"]:
            s["cipher"] = 0 if sell[t] else 1
        else:
            s["cipher"] = int(buy[t])

        if s["cipher_trend"]:
            s["cipher_trend"] = 0 if (sell[t] or not up[t]) else 1
        else:
            s["cipher_trend"] = int(buy[t] and up[t])

        ce_exit = t > 0 and close[t] < stop[t - 1]
        for name, skip in (("cipher_trend_ce", False),
                           ("cipher_full", bool(sqz[t]))):
            if s[name]:
                s[name] = 0 if (ce_exit or not up[t]) else 1
            else:
                s[name] = int(buy[t] and up[t] and not skip)

        if s["cipher_trail"]:
            peak = max(peak, close[t])
            if close[t] < peak - 3 * atr22[t]:
                s["cipher_trail"] = 0
        elif buy[t]:
            s["cipher_trail"], peak = 1, close[t]

        if s["cipher_sqz"]:
            s["cipher_sqz"] = 0 if sell[t] else 1
        else:
            s["cipher_sqz"] = int(buy[t] and not sqz[t])

        for name in out:
            out[name][t] = s[name]
    return {k: pd.Series(v, index=df.index) for k, v in out.items()}


def main():
    prices = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "cipher_layers.csv"
    rows, curves = [], {}
    for path in sorted(glob.glob(os.path.join(prices, "*.csv"))):
        name = os.path.basename(path)[:-4]
        df = load(path, drop_after=LAST_COMPLETE_BAR)
        cost = COSTS.get(name, DEFAULT_COST)
        for variant, pos in positions(df).items():
            rets, trades = returns_from_positions(df, pos, cost)
            rets = rets.iloc[WARMUP:]
            m = metrics(rets, trades, df.iloc[WARMUP:])
            rows.append({"market": name, "variant": variant, **m})
            curves.setdefault(variant, {})[name] = (1 + rets).cumprod()
    res = pd.DataFrame(rows)
    res.to_csv(out_csv, index=False)

    # Equal-weight portfolio of each variant across all markets
    # (daily calendar, curves carried forward on non-trading days).
    port = []
    for variant, by_mkt in curves.items():
        eq = pd.DataFrame(by_mkt).sort_index().ffill().dropna()
        eq = eq.resample("D").last().ffill()
        pe = eq.mean(axis=1)
        pr = pe.pct_change().dropna()
        years = (pe.index[-1] - pe.index[0]).days / 365.25
        dd = (pe / pe.cummax() - 1).min()
        port.append({"variant": variant,
                     "cagr": pe.iloc[-1] ** (1 / years) - 1,
                     "sharpe": pr.mean() / pr.std() * np.sqrt(365),
                     "max_dd": dd})
    pd.DataFrame(port).to_csv(out_csv.replace(".csv", "_portfolio.csv"),
                              index=False)
    pd.set_option("display.width", 200)
    print(res.groupby("variant")[["cagr", "sharpe", "max_dd", "exposure",
                                  "trades", "win_rate", "profit_factor",
                                  "avg_trade"]].median().round(3))
    print(pd.DataFrame(port).round(3))


if __name__ == "__main__":
    main()
