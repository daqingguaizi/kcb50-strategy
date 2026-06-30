"""trix 策略 — 上穿做多 / 下穿平仓"""

import pandas as pd
from indicators import trix, ema


def generate_signals(df: pd.DataFrame, period: int = 9, signal_period: int = 17) -> pd.Series:
    """
    生成交易信号序列。
    
    参数:
        df: 含 close 列的日线数据
        period: trix 计算周期
        signal_period: 信号线平滑周期
    
    返回:
        signals: 1=做多, 0=空仓 (与 df 同 index)
    """
    close = df['close']
    trix_line = trix(close, period)
    signal_line = ema(trix_line, signal_period)

    signals = pd.Series(0, index=df.index, dtype=int)
    position = 0

    for i in range(len(signals)):
        t = trix_line.iloc[i]
        s = signal_line.iloc[i]
        t_prev = trix_line.iloc[i - 1] if i >= 1 else None
        s_prev = signal_line.iloc[i - 1] if i >= 1 else None

        if pd.isna(t) or pd.isna(s):
            signals.iloc[i] = position
            continue

        if position == 0:
            if t_prev is not None and t > s and t_prev <= s_prev:
                position = 1
        else:
            if t_prev is not None and t < s and t_prev >= s_prev:
                position = 0

        signals.iloc[i] = position

    return signals


def get_trades(signals: pd.Series, close: pd.Series) -> list[dict]:
    """从信号序列中提取交易列表"""
    trades = []
    entry_date = entry_price = None

    for i in range(1, len(signals)):
        prev = signals.iloc[i - 1]
        curr = signals.iloc[i]
        date = signals.index[i]
        price = close.iloc[i]
        date_prev = signals.index[i - 1]
        price_prev = close.iloc[i - 1]

        if prev == 0 and curr == 1:
            entry_date = date
            entry_price = price
        elif prev == 1 and curr == 0 and entry_date is not None:
            ret = (price / entry_price - 1)
            trades.append({
                "entry": str(entry_date.date()),
                "exit": str(date.date()),
                "entry_price": round(entry_price, 2),
                "exit_price": round(price, 2),
                "return": ret,
                "days": (date - entry_date).days,
            })
            entry_date = entry_price = None

    # 如果最后还持仓，算浮盈
    if entry_date is not None:
        last_date = signals.index[-1]
        last_price = close.iloc[-1]
        ret = (last_price / entry_price - 1)
        trades.append({
            "entry": str(entry_date.date()),
            "exit": f"{last_date.date()} (持仓中)",
            "entry_price": round(entry_price, 2),
            "exit_price": round(last_price, 2),
            "return": ret,
            "days": (last_date - entry_date).days,
        })

    return trades
