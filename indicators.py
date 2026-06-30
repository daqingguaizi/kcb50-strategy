"""技术指标 — 仅含 ema() 和 trix()，零外部依赖"""

import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def trix(close: pd.Series, period: int = 15) -> pd.Series:
    """三重指数平滑变化率
    TRIX = ROC(EMA3, 1) × 100
    """
    ema1 = ema(close, period)
    ema2 = ema(ema1, period)
    ema3 = ema(ema2, period)
    return ema3.pct_change() * 100.0
