"""Indicator ports from TradingView Pine scripts (default inputs).

Each function takes a daily OHLC DataFrame (columns open/high/low/close) and
returns Series aligned to it. Values at bar t use only data up to bar t.
"""
import numpy as np
import pandas as pd


def ema(s, n):
    # Pine's ta.ema: alpha = 2/(n+1), seeded with the first value.
    return s.ewm(span=n, adjust=False).mean()


def rma(s, n):
    # Pine's ta.rma (Wilder smoothing), used by ta.atr.
    return s.ewm(alpha=1 / n, adjust=False).mean()


def true_range(df):
    prev = df.close.shift(1)
    return pd.concat([df.high - df.low, (df.high - prev).abs(),
                      (df.low - prev).abs()], axis=1).max(axis=1)


def atr(df, n):
    return rma(true_range(df), n)


def wavetrend(df, chlen=9, avg=12, malen=3):
    """VuManChu Cipher B WaveTrend (src = hlc3, wtMALen = 3).

    LazyBear's original WaveTrend uses malen=4; Cipher B's default is 3,
    which shifts cross timing and decides whether a cross counts as a dot.
    """
    ap = (df.high + df.low + df.close) / 3
    esa = ema(ap, chlen)
    d = ema((ap - esa).abs(), chlen)
    ci = (ap - esa) / (0.015 * d)
    wt1 = ema(ci, avg)
    wt2 = wt1.rolling(malen).mean()
    return wt1, wt2


def pine_rma(s, n):
    """Pine ta.rma: seeded with the SMA of the first n values."""
    v = s.to_numpy(dtype=float)
    out = np.full(len(v), np.nan)
    ok = np.flatnonzero(~np.isnan(v))
    if len(ok) >= n:
        f = ok[0]
        out[f + n - 1] = np.mean(v[f:f + n])
        for i in range(f + n, len(v)):
            out[i] = (out[i - 1] * (n - 1) + v[i]) / n
    return pd.Series(out, index=s.index)


def stoch_rsi_k(close, rsi_len=14, stoch_len=14, smooth_k=3, smooth_d=3,
                use_log=True, use_avg=True):
    """Cipher B Stoch RSI line as plotted ("Stoch K").

    Log source, 14/14/3/3, and the plotted K is avg(K, D) (Cipher B's
    "stoch average"). Verified against a TradingView export of QQQ weekly
    (max difference < 0.001).
    """
    src = np.log(close) if use_log else close
    delta = src.diff()
    rsi = 100 - 100 / (1 + pine_rma(delta.clip(lower=0), rsi_len)
                       / pine_rma(-delta.clip(upper=0), rsi_len))
    lo = rsi.rolling(stoch_len).min()
    hi = rsi.rolling(stoch_len).max()
    k = (100 * (rsi - lo) / (hi - lo)).rolling(smooth_k).mean()
    return (k + k.rolling(smooth_d).mean()) / 2 if use_avg else k


def cipher_b_signals(df, ob=53, os_=-53):
    """Cipher B green/red dots: WT cross while WT2 is beyond the OB/OS level."""
    wt1, wt2 = wavetrend(df)
    up = (wt1 > wt2) & (wt1.shift(1) <= wt2.shift(1))
    down = (wt1 < wt2) & (wt1.shift(1) >= wt2.shift(1))
    buy = up & (wt2 <= os_)
    sell = down & (wt2 >= ob)
    return buy, sell


def supertrend(df, period=10, mult=3.0):
    """KivancOzbilgic SuperTrend (src = hl2, ATR = rma). Returns +1 / -1."""
    src = (df.high + df.low) / 2
    a = atr(df, period).to_numpy()
    close = df.close.to_numpy()
    up = (src - mult * a).to_numpy().copy()
    dn = (src + mult * a).to_numpy().copy()
    trend = np.ones(len(df))
    for i in range(1, len(df)):
        if close[i - 1] > up[i - 1]:
            up[i] = max(up[i], up[i - 1])
        if close[i - 1] < dn[i - 1]:
            dn[i] = min(dn[i], dn[i - 1])
        if trend[i - 1] == -1 and close[i] > dn[i - 1]:
            trend[i] = 1
        elif trend[i - 1] == 1 and close[i] < up[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]
    return pd.Series(trend, index=df.index)


def weekly_supertrend(df, period=10, mult=3.0):
    """SuperTrend on weekly bars, mapped to daily bars without lookahead.

    A week's value is only known after its last daily bar, so each daily bar
    sees the trend of the most recent *completed* week.
    """
    wk = df.resample("W-FRI").agg({"open": "first", "high": "max",
                                   "low": "min", "close": "last"}).dropna()
    st = supertrend(wk, period, mult)
    # Index the weekly value at the week's last actual trading day, then
    # shift one daily bar so it applies from the next session.
    last_day = df.index.to_series().resample("W-FRI").last().dropna()
    st.index = last_day.loc[st.index].values
    return st.reindex(df.index).ffill().shift(1)


def chandelier_long_stop(df, length=22, mult=3.0):
    """everget Chandelier Exit long stop (use close for extremums)."""
    raw = (df.close.rolling(length).max() - mult * atr(df, length)).to_numpy().copy()
    close = df.close.to_numpy()
    stop = raw.copy()
    for i in range(1, len(df)):
        if np.isnan(stop[i - 1]):
            continue
        if close[i - 1] > stop[i - 1]:
            stop[i] = max(raw[i], stop[i - 1])
    return pd.Series(stop, index=df.index)


def squeeze_on(df, length=20, bb_mult=2.0, kc_mult=1.5):
    """LazyBear Squeeze Momentum: Bollinger Bands inside Keltner Channels."""
    basis = df.close.rolling(length).mean()
    dev = bb_mult * df.close.rolling(length).std(ddof=0)
    rng = true_range(df).rolling(length).mean()
    return ((basis - dev) > (basis - kc_mult * rng)) & \
           ((basis + dev) < (basis + kc_mult * rng))
