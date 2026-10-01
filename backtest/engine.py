"""Minimal long-only daily backtester.

Signals are evaluated on bar t's close and filled at bar t+1's open, so no
bar ever trades on information it could not have had.
"""
import numpy as np
import pandas as pd


def load(path, drop_after=None):
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if drop_after is not None:
        df = df[df.index <= pd.Timestamp(drop_after)]
    return df[["open", "high", "low", "close"]].astype(float)


def returns_from_positions(df, pos, cost):
    """pos[t] = position decided at close of bar t (0 or 1).

    Returns the strategy's per-bar return series and the list of trades as
    (entry_date, exit_date, return).
    """
    o, c = df.open.to_numpy(), df.close.to_numpy()
    held = np.r_[0, pos.to_numpy()[:-1]]  # position during each bar's session
    r = np.zeros(len(df))
    trades, entry_px, entry_i = [], None, None
    for t in range(1, len(df)):
        if held[t] and held[t - 1]:
            r[t] = c[t] / c[t - 1] - 1
        elif held[t]:
            r[t] = c[t] / o[t] - 1 - cost
            entry_px, entry_i = o[t], t
        elif held[t - 1]:
            r[t] = o[t] / c[t - 1] - 1 - cost
            trades.append((df.index[entry_i], df.index[t],
                           (o[t] / entry_px) * (1 - cost) ** 2 - 1))
    if held[-1] and entry_px is not None:  # mark open trade at last close
        trades.append((df.index[entry_i], df.index[-1],
                       (c[-1] / entry_px) * (1 - cost) ** 2 - 1))
    return pd.Series(r, index=df.index), trades


def metrics(rets, trades, df):
    eq = (1 + rets).cumprod()
    years = (df.index[-1] - df.index[0]).days / 365.25
    per_year = len(rets) / years
    cagr = eq.iloc[-1] ** (1 / years) - 1
    vol = rets.std() * np.sqrt(per_year)
    sharpe = rets.mean() * per_year / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    tr = np.array([t[2] for t in trades])
    wins, losses = tr[tr > 0].sum(), -tr[tr < 0].sum()
    return {
        "cagr": cagr,
        "total": eq.iloc[-1] - 1,
        "sharpe": sharpe,
        "max_dd": dd,
        "calmar": cagr / -dd if dd < 0 else np.nan,
        "exposure": (rets != 0).mean(),
        "trades": len(tr),
        "win_rate": (tr > 0).mean() if len(tr) else np.nan,
        "profit_factor": wins / losses if losses > 0 else np.nan,
        "avg_trade": tr.mean() if len(tr) else np.nan,
    }
