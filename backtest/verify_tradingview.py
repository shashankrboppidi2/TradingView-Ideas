#!/usr/bin/env python3
"""Check the Cipher B port against TradingView "Export chart data" files.

Each export must contain the VuManChu Cipher B plots (WT Wave 1/2, Stoch K,
Buy circle, Sell circle). Indicator values are recomputed from the export's
own OHLC and compared value by value and dot by dot.

Usage: python3 backtest/verify_tradingview.py data/tradingview/*.csv
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind  # noqa: E402

WARM = 100  # bars skipped while the indicators settle


def main():
    for path in sys.argv[1:]:
        d = pd.read_csv(path, parse_dates=["time"]).set_index("time")
        w1, w2 = ind.wavetrend(d)
        k = ind.stoch_rsi_k(d.close)
        buy, sell = ind.cipher_b_signals(d)
        tb, ts = d["Buy circle"].notna(), d["Sell circle"].notna()
        err = lambda a, b: (a - b).abs().iloc[WARM:].max()  # noqa: E731
        print(f"{os.path.basename(path)}: {len(d)} bars "
              f"{d.index[0].date()}..{d.index[-1].date()}")
        print(f"  max |diff|  WT1 {err(w1, d['WT Wave 1']):.4f}  "
              f"WT2 {err(w2, d['WT Wave 2']):.4f}  "
              f"Stoch K {err(k, d['Stoch K']):.4f}")
        for label, mine, tv in (("buy", buy, tb), ("sell", sell, ts)):
            extra = mine & ~tv
            missing = tv & ~mine
            print(f"  {label} circles: TradingView {int(tv.sum())}, "
                  f"ours {int(mine.sum())}, matched {int((mine & tv).sum())}"
                  + (f"; only ours: {[t.date().isoformat() for t in d.index[extra]]}"
                     if extra.any() else "")
                  + (f"; only TradingView: {[t.date().isoformat() for t in d.index[missing]]}"
                     if missing.any() else ""))


if __name__ == "__main__":
    main()
