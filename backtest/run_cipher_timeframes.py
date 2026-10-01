#!/usr/bin/env python3
"""Cipher B on daily vs weekly bars, over the same dates.

Weekly signals are evaluated on the week's last daily close and filled at the
next session's open. All variants start after the weekly warmup so they cover
identical periods.

Variants (long-only, default Cipher B settings):
  buy_hold      hold throughout
  daily_cipher  daily buy dot in, daily sell dot out
  weekly_cipher weekly buy dot in, weekly sell dot out
  weekly_cipher_st  weekly buy dot in; out on weekly sell dot or when weekly
                    SuperTrend(10,3) turns down

Usage: python3 backtest/run_cipher_timeframes.py PRICES_DIR [OUT_CSV]
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from engine import load, metrics, returns_from_positions  # noqa: E402
from run_cipher_layers import COSTS, DEFAULT_COST, LAST_COMPLETE_BAR  # noqa: E402

WEEKLY_WARMUP = 30  # weeks


def to_daily(weekly, df):
    """Place each weekly value on that week's last trading day."""
    last_day = df.index.to_series().resample("W-FRI").last().dropna()
    s = weekly.copy()
    s.index = last_day.loc[weekly.index].values
    return s.reindex(df.index)


def run_state(entry, exit_, start):
    pos = np.zeros(len(entry))
    held = 0
    for t in range(start, len(entry)):
        held = (0 if exit_[t] else 1) if held else int(entry[t])
        pos[t] = held
    return pos


def positions(df):
    wk = df.resample("W-FRI").agg({"open": "first", "high": "max",
                                   "low": "min", "close": "last"}).dropna()
    wbuy, wsell = ind.cipher_b_signals(wk)
    wst = ind.supertrend(wk)
    wbuy = to_daily(wbuy, df).fillna(False).astype(bool).to_numpy()
    wsell = to_daily(wsell, df).fillna(False).astype(bool).to_numpy()
    wdown = (to_daily(wst, df).ffill() == -1).to_numpy()
    dbuy, dsell = (s.to_numpy() for s in ind.cipher_b_signals(df))

    week_ends = to_daily(wk.close, df).dropna().index
    start = df.index.get_loc(week_ends[WEEKLY_WARMUP])
    out = {
        "buy_hold": run_state(np.ones(len(df)), np.zeros(len(df)), start),
        "daily_cipher": run_state(dbuy, dsell, start),
        "weekly_cipher": run_state(wbuy, wsell, start),
        "weekly_cipher_st": run_state(wbuy, wsell | wdown, start),
    }
    return {k: pd.Series(v, index=df.index) for k, v in out.items()}, start


def main():
    prices = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "cipher_timeframes.csv"
    rows, curves = [], {}
    for path in sorted(glob.glob(os.path.join(prices, "*.csv"))):
        name = os.path.basename(path)[:-4]
        df = load(path, drop_after=LAST_COMPLETE_BAR)
        cost = COSTS.get(name, DEFAULT_COST)
        pos, start = positions(df)
        for variant, p in pos.items():
            rets, trades = returns_from_positions(df, p, cost)
            rets = rets.iloc[start:]
            m = metrics(rets, trades, df.iloc[start:])
            rows.append({"market": name, "variant": variant,
                         "start": df.index[start].date(), **m})
            curves.setdefault(variant, {})[name] = (1 + rets).cumprod()
    res = pd.DataFrame(rows)
    res.to_csv(out_csv, index=False)

    port = []
    for variant, by_mkt in curves.items():
        eq = pd.DataFrame(by_mkt).sort_index().ffill().dropna()
        eq = eq.resample("D").last().ffill()
        pe = eq.mean(axis=1)
        pr = pe.pct_change().dropna()
        years = (pe.index[-1] - pe.index[0]).days / 365.25
        port.append({"variant": variant,
                     "cagr": pe.iloc[-1] ** (1 / years) - 1,
                     "sharpe": pr.mean() / pr.std() * np.sqrt(365),
                     "max_dd": (pe / pe.cummax() - 1).min()})
    pd.set_option("display.width", 200)
    print(res.groupby("variant")[["cagr", "sharpe", "max_dd", "exposure",
                                  "trades", "win_rate", "profit_factor",
                                  "avg_trade"]].median().round(3))
    print(pd.DataFrame(port).round(3))


if __name__ == "__main__":
    main()
