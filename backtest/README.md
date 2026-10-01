# Backtests

Long-only daily backtests of TradingView community indicators, using their
default settings. Signals are taken on the close and filled at the next open.
Costs are 0.05% per side (0.02% FX, 0.10% crypto).

Price data comes from the Interactive Brokers connector (5 years of daily
bars, the connector's maximum) and is kept out of git. Expected layout:
`PRICES_DIR/<MARKET>.csv` with `date,open,high,low,close,volume`.

```
python3 backtest/run_cipher_layers.py PRICES_DIR results.csv
```

## Run 1: VuManChu Cipher B with add-ons (Oct 2021 – Sep 2026, 14 markets)

Markets: SPY, QQQ, IWM, TLT, GLD, AAPL, MSFT, NVDA, XLE, USO, EURUSD,
XAUUSD, BTC, ETH. Prices are not dividend-adjusted.

Equal-weight portfolio across all 14 markets:

| Variant | CAGR | Sharpe | Max DD | Median exposure |
|---|---|---|---|---|
| Buy and hold | 20.2% | 1.04 | -28.7% | 100% |
| Weekly SuperTrend(10,3) only | 15.8% | **1.08** | **-18.6%** | 60% |
| Cipher B (buy dot in, sell dot out) | 7.8% | 0.69 | -19.8% | 44% |
| Cipher B + 3×ATR trail from entry | 6.8% | 0.70 | -18.4% | — |
| Cipher B + squeeze filter | 8.7% | 0.76 | -19.8% | — |
| Cipher B + weekly SuperTrend filter | 3.3% | 0.59 | -9.2% | 16% |
| … + Chandelier Exit (as published) | 1.4% | 0.52 | -3.9% | 6% |
| … + squeeze filter | 1.4% | 0.57 | -3.2% | 5% |

Findings:
- Cipher B's buy dots are well timed (median 74% win rate, profit factor
  3.8, +2.9% per trade) but it sits in cash more than half the time, so it
  trails buy-and-hold on both return and Sharpe.
- A weekly trend filter hurts Cipher B: its best buys come right after
  selloffs, when the weekly trend has already turned down.
- Chandelier Exit as published (highest close of the last 22 bars) exits
  almost immediately after an oversold entry; a trail anchored at entry is
  the usable form, and it did not improve risk-adjusted returns.
- The squeeze filter skipped 1 of 128 trades; the difference is noise.
- About 9 Cipher B trades per market in 5 years: differences between Cipher
  variants are within noise. One mostly-bullish regime; needs longer data.
