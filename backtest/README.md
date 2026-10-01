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

## Run 2: Cipher B on daily vs weekly bars (May 2022 – Sep 2026)

```
python3 backtest/run_cipher_timeframes.py PRICES_DIR results.csv
```

Weekly signals fire on the week's last close and fill at the next open. All
variants start after a 30-week warmup (2022-05-06).

| Variant | CAGR | Sharpe | Max DD | Excl. ETH: CAGR / Sharpe |
|---|---|---|---|---|
| Buy and hold | 23.5% | 1.14 | -22.5% | 24.8% / 1.23 |
| Daily Cipher B | 8.1% | 0.77 | -13.2% | 9.0% / 0.88 |
| Weekly Cipher B | 14.5% | **1.23** | -17.0% | 8.7% / 1.04 |
| Weekly Cipher B + weekly SuperTrend exit | 1.2% | 0.67 | -1.8% | — |

- Weekly: 33 trades, 29 winners, median +20.5%, average hold ~7.5 months.
- Most weekly buys came in two clusters (Jun–Aug 2022 and Apr–May 2025)
  across correlated markets, so there are only a few independent events.
- The Sharpe lead over buy-and-hold depends on ETH (+137% on one trade);
  without ETH it falls behind.
- Monthly Cipher B produced zero buy dots in 30 usable months: untestable
  without decades of data.
- The SuperTrend exit fails for the same reason as in run 1: weekly buy
  dots occur while the weekly trend is still down.

## Run 3: weekly Cipher B add-on vs weekly SuperTrend, Nasdaq-100 + ETFs (1999 – Sep 2026)

```
python3 backtest/run_weekly_addon.py WEEKLY_PRICES_DIR out_prefix
```

Weekly bars from the IBKR connector (max 1,000 bars per request, so most
series start 2007 or earlier; some start later because of ticker changes or
connector limits). 104 markets: ~93 current Nasdaq-100 members plus SPY, QQQ,
IWM, TLT, GLD, XLE, USO, EURUSD, BTC, ETH. Not available: AEP, LIN, DASH
(connector errors), EA (delisted), XAUUSD (no data subscription). Too short
(<3 years): ARM, AZN, SPCX. Data fixes are listed in `START_AFTER` in the
script (mis-scaled history for MSTR/FTNT, bad prints for CMCSA/WBD, KDP's
unadjusted 2018 special dividend); stray high/low prints are clipped.

Equal-weight portfolio of all markets available each week (584 Cipher B
add-on entries in total):

| Variant | CAGR | Sharpe | Max DD | Sharpe 2007–13 | 2014–19 | 2020–26 | Avg exposure |
|---|---|---|---|---|---|---|---|
| Buy and hold | 17.3% | **0.80** | -48.0% | 0.78 | **1.42** | **0.99** | 100% |
| Weekly SuperTrend | 7.7% | 0.68 | -51.9% | **0.94** | 1.14 | 0.94 | 61% |
| 50% hold + 50% Cipher add-on | 12.2% | 0.78 | -39.3% | 0.70 | 1.40 | 0.94 | 65% |
| 50% SuperTrend + 50% Cipher add-on | 7.3% | 0.76 | **-24.6%** | 0.85 | 1.25 | 0.97 | 46% |
| 100% if SuperTrend up or Cipher add-on open | 13.3% | **0.80** | -39.5% | 0.86 | 1.27 | 0.97 | 82% |

Index ETFs (no survivorship bias):

| | QQQ CAGR / Sharpe / Max DD | SPY CAGR / Sharpe / Max DD |
|---|---|---|
| Buy and hold | 15.5% / **0.81** / -49.6% | 9.1% / 0.57 / -56.0% |
| Weekly SuperTrend | 8.1% / 0.63 / **-25.9%** | 6.5% / **0.62** / **-22.5%** |
| 50% SuperTrend + 50% Cipher add-on | 4.5% / 0.52 / -32.1% | 4.3% / 0.54 / -35.0% |

Findings:
- The strong 4-year result for the 50/50 SuperTrend + Cipher combination
  (Sharpe 1.45, run on the 14-market set) does not hold over the longer
  history: Sharpe 0.76 vs 0.80 for buy-and-hold. Its lasting benefit is
  roughly half the drawdown (-24.6% vs -48%) at ~46% average exposure.
- Against SuperTrend alone, the Cipher add-on variants have a higher Sharpe
  in 65–71% of markets and at the portfolio level, so Cipher B timing adds
  something to pure trend following on individual stocks.
- On the index ETFs (QQQ, SPY) the Cipher add-on did not help: SuperTrend
  alone gave the better risk-adjusted result and the smallest drawdowns.
- Survivorship bias: today's Nasdaq-100 members are past winners, which
  flatters buy-and-hold on single stocks. QQQ and SPY are the cleaner test.

## Run 4: hold QQQ, add 25% leverage on weekly Cipher B signals (Nov 2007 – Sep 2026)

```
python3 backtest/run_qqq_leverage.py WEEKLY_PRICES_DIR QQQ
```

Lever up on a weekly green dot (WT cross up, WT2 <= -53); lever down on a
weekly red dot at the overbought line (WT cross down, WT2 >= +53) with Stoch
RSI %K >= 80. Margin interest ≈ annual Fed funds average + 1.5% (approximate
rates hard-coded in the script). Calls are simulated with Black-Scholes
(IV = 26-week realized vol × 1.1, 2% spread per side), since no historical
options data is available.

| QQQ | CAGR | Sharpe | Max DD | $1 grows to |
|---|---|---|---|---|
| Buy and hold | 15.5% | **0.81** | **-49.6%** | 15.1 |
| Constant 125% (margin) | **18.0%** | 0.78 | -58.9% | **22.7** |
| 125% on signal (margin) | 15.1% | 0.75 | -56.7% | 14.3 |
| Calls on signal (25% financed) | 13.5% | 0.59 | -73.4% | 10.8 |
| 125% at random times (median of 1,000) | 15.9% | 0.80 | -49.6% | 16.3 |

Only 4 signal windows in 19 years: Mar 2008 → Jul 2009 (QQQ -15%, calls
-84%), Jan → May 2019 (+13%, +52%), Mar 2022 → May 2023 (-8%, -83%),
May → Aug 2025 (+21%, +82%). The signal's timing beat only 8% of random
timings. Looser entry/exit definitions (any green dot below zero; any red dot;
with or without the Stoch RSI condition) and SPY gave the same picture: no
variant beat buy-and-hold on Sharpe, and all had deeper drawdowns.
