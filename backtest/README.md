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

> **Correction (Oct 2026):** earlier versions of these results used
> WaveTrend's signal line with a 4-bar SMA (LazyBear's original WaveTrend)
> and Stoch RSI on raw closes. VuManChu Cipher B uses a 3-bar SMA
> (`wtMALen = 3`) and Stoch RSI on log closes. The 4-bar version missed
> signals such as QQQ's weekly green dot in the week of 2026-04-06
> (WT2 = -51.5 instead of -54.8). All tables below were re-run with the
> Cipher B defaults.

## Run 1: VuManChu Cipher B with add-ons (Oct 2021 – Sep 2026, 14 markets)

Markets: SPY, QQQ, IWM, TLT, GLD, AAPL, MSFT, NVDA, XLE, USO, EURUSD,
XAUUSD, BTC, ETH. Prices are not dividend-adjusted.

Equal-weight portfolio across all 14 markets:

| Variant | CAGR | Sharpe | Max DD | Median exposure |
|---|---|---|---|---|
| Buy and hold | 20.2% | **1.04** | -28.7% | 100% |
| Weekly SuperTrend(10,3) only | 15.8% | **1.08** | -18.6% | 60% |
| Cipher B (buy dot in, sell dot out) | 7.1% | 0.66 | -19.2% | 45% |
| Cipher B + 3×ATR trail from entry | 11.3% | 0.99 | -18.2% | 54% |
| Cipher B + squeeze filter | 7.6% | 0.69 | -19.2% | 45% |
| Cipher B + weekly SuperTrend filter | 3.1% | 0.56 | -9.1% | 17% |
| … + Chandelier Exit (as published) | 0.2% | 0.13 | -3.7% | 6% |
| … + squeeze filter | 0.1% | 0.12 | -2.2% | 5% |

Findings:
- Cipher B's daily buy dots are well timed (median 73% win rate, profit
  factor 3.1, +3.2% per trade) but it sits in cash more than half the time.
- Exiting on a 3×ATR trail from entry instead of the sell dot lets winners
  run and brings Cipher B close to buy-and-hold on Sharpe (0.99 vs 1.04).
- A weekly trend filter hurts Cipher B: its best buys come right after
  selloffs, when the weekly trend has already turned down.
- Chandelier Exit as published (highest close of the last 22 bars) exits
  almost immediately after an oversold entry.
- The squeeze filter skipped 1 of 135 trades; the difference is noise.
- About 10 Cipher B trades per market in 5 years; one mostly-bullish regime.

## Run 2: Cipher B on daily vs weekly bars (May 2022 – Sep 2026)

```
python3 backtest/run_cipher_timeframes.py PRICES_DIR results.csv
```

Weekly signals fire on the week's last close and fill at the next open. All
variants start after a 30-week warmup (2022-05-06).

| Variant | CAGR | Sharpe | Max DD | Excl. ETH: CAGR / Sharpe |
|---|---|---|---|---|
| Buy and hold | 23.5% | 1.14 | -22.5% | 24.8% / **1.23** |
| Daily Cipher B | 7.5% | 0.71 | -13.5% | 8.3% / 0.81 |
| Weekly Cipher B | 17.4% | **1.35** | -17.3% | 9.2% / 1.06 |
| Weekly Cipher B + weekly SuperTrend exit | 1.7% | 0.82 | -2.7% | — |

- Weekly: 38 trades, 34 winners, median +16.8%.
- Most weekly buys cluster around a few market-wide lows (mid-2022,
  April 2025, April 2026), so there are few independent events.
- The Sharpe lead over buy-and-hold depends on ETH; without ETH it trails.
- Monthly Cipher B produced zero buy dots in 30 usable months.

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

Equal-weight portfolio of all markets available each week (608 Cipher B
add-on entries in total):

| Variant | CAGR | Sharpe | Max DD | Sharpe 2007–13 | 2014–19 | 2020–26 | Avg exposure |
|---|---|---|---|---|---|---|---|
| Buy and hold | 17.3% | **0.80** | -48.0% | 0.78 | **1.42** | **0.99** | 100% |
| Weekly SuperTrend | 7.7% | 0.68 | -51.9% | **0.94** | 1.14 | 0.94 | 61% |
| 50% hold + 50% Cipher add-on | 12.1% | 0.77 | -39.2% | 0.71 | 1.39 | 0.95 | 66% |
| 50% SuperTrend + 50% Cipher add-on | 7.3% | 0.75 | **-25.3%** | 0.85 | 1.24 | 0.98 | 46% |
| 100% if SuperTrend up or Cipher add-on open | 13.4% | **0.80** | -40.1% | 0.87 | 1.26 | 0.98 | 82% |

Index ETFs (no survivorship bias):

| | QQQ CAGR / Sharpe / Max DD | SPY CAGR / Sharpe / Max DD |
|---|---|---|
| Buy and hold | 15.5% / **0.81** / -49.6% | 9.1% / 0.57 / -56.0% |
| Weekly SuperTrend | 8.1% / 0.63 / **-25.9%** | 6.5% / **0.62** / **-22.5%** |
| 50% SuperTrend + 50% Cipher add-on | 4.9% / 0.56 / -32.1% | 4.4% / 0.54 / -34.1% |

Findings:
- Over the long history no variant beats buy-and-hold on Sharpe. The 50/50
  SuperTrend + Cipher combination's lasting benefit is roughly half the
  drawdown (-25% vs -48%) at ~46% average exposure.
- Against SuperTrend alone, the Cipher add-on variants have a higher Sharpe
  in 67–72% of markets, so Cipher B timing adds something to pure trend
  following on individual stocks.
- On QQQ and SPY the Cipher add-on did not help: SuperTrend alone gave the
  better risk-adjusted result and the smallest drawdowns.
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
| 125% on signal (margin) | 15.4% | 0.75 | -56.7% | 14.8 |
| Calls on signal (25% financed) | 15.0% | 0.63 | -73.4% | 13.9 |
| 125% at random times (median of 1,000) | 16.0% | 0.80 | -49.6% | 16.3 |

Signal windows (fill weeks): Mar 2008 → Jun 2009 (QQQ -17%, calls -85%),
Jan → May 2019 (+13%, +52%), Mar 2022 → May 2023 (-8%, -83%),
May → Aug 2025 (+18%, +72%), Apr → Jun 2026 (+21%, +156%). The signal's
timing beat 14% of random timings.

Why leverage was held through 2008–09 and 2022: in a bear market, rallies
stall before WaveTrend reaches +53, so the overbought red dot does not
appear until the next bull market (max WT2 during the 2022 window before
April 2023 was +34). Exiting on any red dot with Stoch RSI %K >= 80 cuts
2008 short (exit June 2008) and gives QQQ 15.8% CAGR / Sharpe 0.79 / Max DD
-50.4%. Other entry/exit definitions and SPY gave the same picture: no
variant beat buy-and-hold on Sharpe.

## Run 5: hold QQQ, buy LEAPS on weekly green dots and hold to expiry (Nov 2007 – Sep 2026)

```
python3 backtest/run_qqq_leaps.py WEEKLY_PRICES_DIR QQQ
```

On each weekly green dot, borrow 25% of equity and buy QQQ calls at the next
open; hold to expiry, then repay the loan and reinvest the rest in QQQ. One
position at a time unless "stack" (every green dot adds a position). Black-
Scholes pricing with IV = ½ × (26-week realized vol × 1.1) + ½ × 22%, 2%
spread on purchase; mark-to-model in between. "Random" buys the same LEAPS
on random weeks (300 runs).

Green dots (week of): 2008-02-25, 2008-03-17, 2008-10-27, 2008-11-24,
2019-01-07, 2022-03-14, 2022-05-30, 2022-06-20, 2025-04-21, 2026-04-06.

| QQQ | CAGR | Sharpe | Max DD | $1 grows to | Beats random |
|---|---|---|---|---|---|
| Buy and hold | 15.5% | **0.81** | **-49.6%** | 15.1 | — |
| Constant 125% (margin) | 18.0% | 0.78 | -58.9% | 22.7 | — |
| 1-year ATM LEAPS on signal | 14.0% | 0.60 | -74.1% | 11.8 | 4% |
| 1-year ATM at random weeks (median) | 19.9% | 0.70 | -64.3% | 30.6 | — |
| 2-year ATM LEAPS on signal | 19.2% | 0.70 | -71.9% | 27.3 | 28% |
| 2-year 10% ITM LEAPS on signal | 19.2% | 0.71 | -71.1% | 27.4 | 30% |
| 2-year ATM at random weeks (median) | 21.0% | 0.73 | -61.9% | 36.4 | — |
| 2-year ATM, stacked on every dot | **23.7%** | 0.57 | -96.3% | **55.2** | — |

2-year ATM trades: Mar 2008 → Mar 2010 (QQQ +5%, calls -72%), Jan 2019 →
Jan 2021 (+98%, +479%), Mar 2022 → Mar 2024 (+25%, +50%), May 2025 → open
(+57% so far). 1-year LEAPS bought in Mar 2008 and Mar 2022 expired
worthless. Stacking borrowed 100% of equity across four 2008 dots; the -96%
drawdown would have meant margin calls in practice.
