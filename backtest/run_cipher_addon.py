#!/usr/bin/env python3
"""Weekly Cipher B as an add-to-position signal vs weekly SuperTrend.

All signals are on weekly bars, evaluated on the week's last close and
filled at the next open. Maximum exposure is 100% in every variant.

  buy_hold        100% throughout
  supertrend      100% while weekly SuperTrend(10,3) is up
  core_bh_add     50% always + 50% from Cipher B buy dot until sell dot
  core_st_add     50% while SuperTrend up + 50% Cipher B add-on as above
  st_or_cipher    100% while SuperTrend is up OR a Cipher B add-on is open

Usage: python3 backtest/run_cipher_addon.py PRICES_DIR [OUT_CSV]
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from engine import load, returns_weighted  # noqa: E402
from run_cipher_layers import COSTS, DEFAULT_COST, LAST_COMPLETE_BAR  # noqa: E402
from run_cipher_timeframes import WEEKLY_WARMUP, to_daily  # noqa: E402


def weights(df):
    wk = df.resample("W-FRI").agg({"open": "first", "high": "max",
                                   "low": "min", "close": "last"}).dropna()
    buy, sell = ind.cipher_b_signals(wk)
    st_up = to_daily(ind.supertrend(wk) == 1, df).ffill().fillna(False)
    buy = to_daily(buy, df).fillna(False).astype(bool).to_numpy()
    sell = to_daily(sell, df).fillna(False).astype(bool).to_numpy()
    st_up = st_up.astype(bool).to_numpy()
    start = df.index.get_loc(to_daily(wk.close, df).dropna()
                             .index[WEEKLY_WARMUP])

    n = len(df)
    addon = np.zeros(n)
    on = 0
    for t in range(start, n):
        on = (0 if sell[t] else 1) if on else int(buy[t])
        addon[t] = on
    live = np.arange(n) >= start
    st = st_up * live
    w = {
        "buy_hold": live * 1.0,
        "supertrend": st * 1.0,
        "core_bh_add": live * 0.5 + 0.5 * addon,
        "core_st_add": 0.5 * st + 0.5 * addon,
        "st_or_cipher": np.maximum(st, addon) * 1.0,
    }
    return {k: pd.Series(v, index=df.index) for k, v in w.items()}, start


def stats(rets, index):
    eq = (1 + rets).cumprod()
    years = (index[-1] - index[0]).days / 365.25
    per_year = len(rets) / years
    vol = rets.std() * np.sqrt(per_year)
    dd = (eq / eq.cummax() - 1).min()
    return {"cagr": eq.iloc[-1] ** (1 / years) - 1,
            "sharpe": rets.mean() * per_year / vol if vol else np.nan,
            "max_dd": dd}


def portfolio(curves, exclude=()):
    eq = pd.DataFrame({k: v for k, v in curves.items() if k not in exclude})
    eq = eq.sort_index().ffill().dropna().resample("D").last().ffill()
    pe = eq.mean(axis=1)
    pr = pe.pct_change().dropna()
    years = (pe.index[-1] - pe.index[0]).days / 365.25
    return {"cagr": pe.iloc[-1] ** (1 / years) - 1,
            "sharpe": pr.mean() / pr.std() * np.sqrt(365),
            "max_dd": (pe / pe.cummax() - 1).min()}


def main():
    prices = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "cipher_addon.csv"
    rows, curves = [], {}
    for path in sorted(glob.glob(os.path.join(prices, "*.csv"))):
        name = os.path.basename(path)[:-4]
        df = load(path, drop_after=LAST_COMPLETE_BAR)
        cost = COSTS.get(name, DEFAULT_COST)
        ws, start = weights(df)
        for variant, w in ws.items():
            rets = returns_weighted(df, w, cost).iloc[start:]
            rows.append({"market": name, "variant": variant,
                         "avg_exposure": w.iloc[start:].mean(),
                         **stats(rets, df.index[start:])})
            curves.setdefault(variant, {})[name] = (1 + rets).cumprod()
    res = pd.DataFrame(rows)
    res.to_csv(out_csv, index=False)

    pd.set_option("display.width", 200)
    order = list(curves)
    for excl in ((), ("ETH",)):
        tab = pd.DataFrame({v: portfolio(curves[v], excl) for v in order}).T
        tab["avg_exposure"] = res.groupby("variant").avg_exposure.mean()
        print("portfolio" + (f" excluding {', '.join(excl)}" if excl else ""))
        print(tab.round(3))
    print(res.pivot(index="market", columns="variant",
                    values="sharpe")[order].round(2))


if __name__ == "__main__":
    main()
