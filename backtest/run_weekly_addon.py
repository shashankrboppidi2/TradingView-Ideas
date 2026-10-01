#!/usr/bin/env python3
"""Weekly Cipher B add-on vs weekly SuperTrend on long weekly histories.

Input is weekly OHLC bars (one CSV per market). Bars are normalised to
Friday-ending weeks. Weights are decided on a week's close and applied from
the next week's open. Maximum exposure is 100% in every variant.

  buy_hold      100% throughout
  supertrend    100% while weekly SuperTrend(10,3) is up
  core_bh_add   50% always + 50% from Cipher B buy dot until sell dot
  core_st_add   50% while SuperTrend up + 50% Cipher B add-on
  st_or_cipher  100% while SuperTrend is up OR a Cipher B add-on is open

The portfolio is equal-weight across whichever markets have started, re-
balanced weekly, so markets with shorter histories join when they list.

Usage: python3 backtest/run_weekly_addon.py WEEKLY_PRICES_DIR [OUT_PREFIX]
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402
from engine import returns_weighted  # noqa: E402

WARMUP = 30          # weeks before trading
MIN_WEEKS = 156      # skip markets with < 3 years after warmup
LAST_WEEK = "2026-09-25"  # last complete week (the current week is forming)
COSTS = {"BTC": 0.001, "ETH": 0.001, "EURUSD": 0.0002}
DEFAULT_COST = 0.0005
VARIANTS = ["buy_hold", "supertrend", "core_bh_add", "core_st_add",
            "st_or_cipher"]
PERIODS = [("2007-2013", "2007-01-01", "2013-12-31"),
           ("2014-2019", "2014-01-01", "2019-12-31"),
           ("2020-2026", "2020-01-01", "2026-12-31")]


def load_weekly(path):
    d = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    wk = d.resample("W-FRI").agg({"open": "first", "high": "max",
                                  "low": "min", "close": "last"}).dropna()
    return wk[wk.index <= pd.Timestamp(LAST_WEEK)].astype(float)


def weights(wk):
    buy, sell = (s.to_numpy() for s in ind.cipher_b_signals(wk))
    up = (ind.supertrend(wk) == 1).to_numpy()
    n = len(wk)
    addon = np.zeros(n)
    on = 0
    for t in range(WARMUP, n):
        on = (0 if sell[t] else 1) if on else int(buy[t])
        addon[t] = on
    live = (np.arange(n) >= WARMUP).astype(float)
    st = up * live
    w = {"buy_hold": live,
         "supertrend": st,
         "core_bh_add": 0.5 * live + 0.5 * addon,
         "core_st_add": 0.5 * st + 0.5 * addon,
         "st_or_cipher": np.maximum(st, addon)}
    return {k: pd.Series(v, index=wk.index) for k, v in w.items()}, addon


def stats(r):
    r = r.dropna()
    if len(r) < 2:
        return {"cagr": np.nan, "sharpe": np.nan, "max_dd": np.nan}
    eq = (1 + r).cumprod()
    years = len(r) / 52.18
    sd = r.std()
    return {"cagr": eq.iloc[-1] ** (1 / years) - 1,
            "sharpe": r.mean() / sd * np.sqrt(52.18) if sd else np.nan,
            "max_dd": (eq / eq.cummax() - 1).min()}


def main():
    src = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else "weekly_addon"
    rows, rets, skipped, adds = [], {v: {} for v in VARIANTS}, [], 0
    for path in sorted(glob.glob(os.path.join(src, "*.csv"))):
        name = os.path.basename(path)[:-4]
        wk = load_weekly(path)
        if len(wk) < WARMUP + MIN_WEEKS:
            skipped.append(name)
            continue
        ws, addon = weights(wk)
        adds += int((np.diff(addon) == 1).sum())
        cost = COSTS.get(name, DEFAULT_COST)
        for v in VARIANTS:
            r = returns_weighted(wk, ws[v], cost).iloc[WARMUP + 1:]
            rets[v][name] = r
            rows.append({"market": name, "variant": v,
                         "start": r.index[0].date(), "weeks": len(r),
                         "avg_exposure": ws[v].iloc[WARMUP:].mean(),
                         **stats(r)})
    res = pd.DataFrame(rows)
    res.to_csv(f"{prefix}_markets.csv", index=False)

    port = {v: pd.DataFrame(rets[v]).sort_index().mean(axis=1)
            for v in VARIANTS}
    summary = []
    for v in VARIANTS:
        row = {"variant": v, **stats(port[v])}
        for label, a, b in PERIODS:
            row[f"sharpe_{label}"] = stats(port[v][a:b])["sharpe"]
        sub = res[res.variant == v].set_index("market")
        row["median_mkt_sharpe"] = sub.sharpe.median()
        row["avg_exposure"] = sub.avg_exposure.mean()
        summary.append(row)
    summ = pd.DataFrame(summary).set_index("variant")
    summ.to_csv(f"{prefix}_summary.csv")

    piv = res.pivot(index="market", columns="variant", values="sharpe")
    beats = {v: (piv[v] > piv["buy_hold"]).mean() for v in VARIANTS[1:]}
    beats_st = {v: (piv[v] > piv["supertrend"]).mean()
                for v in VARIANTS[2:]}
    pd.set_option("display.width", 220)
    print(f"markets: {piv.shape[0]}  skipped (<3y): {skipped}  "
          f"Cipher add-on entries: {adds}")
    print(f"portfolio span: {port['buy_hold'].index[0].date()} .. "
          f"{port['buy_hold'].index[-1].date()}")
    print(summ.round(3))
    print("share of markets with higher Sharpe than buy_hold:",
          {k: round(x, 2) for k, x in beats.items()})
    print("share of markets with higher Sharpe than supertrend:",
          {k: round(x, 2) for k, x in beats_st.items()})


if __name__ == "__main__":
    main()
