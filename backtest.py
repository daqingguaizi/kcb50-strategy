"""回测引擎 — 信号 → 净值曲线 + 绩效指标"""

import numpy as np
import pandas as pd


def compute_equity(signals: pd.Series, close: pd.Series,
                   initial_capital: float = 1_000_000) -> pd.Series:
    """从信号序列计算净值曲线"""
    # 持仓收益 = 日收益率 × 前一天信号
    daily_ret = close.pct_change().fillna(0)
    position = signals.shift(1).fillna(0)
    strategy_ret = daily_ret * position

    equity = (1 + strategy_ret).cumprod() * initial_capital
    equity.iloc[0] = initial_capital
    return equity


def compute_metrics(equity: pd.Series, trades: list[dict] = None) -> dict:
    """计算全套绩效指标"""
    n = len(equity)
    if n < 2:
        return {}

    nav = equity / equity.iloc[0]
    daily_ret = nav.pct_change().fillna(0)

    total_return = float(nav.iloc[-1] - 1)
    years = n / 252
    annual_return = float((nav.iloc[-1]) ** (1 / max(years, 0.5)) - 1)
    annual_vol = float(daily_ret.std() * np.sqrt(252))
    sharpe = (annual_return - 0.03) / max(annual_vol, 1e-8)

    # 最大回撤
    peak = nav.cummax()
    drawdowns = 1 - nav / peak
    max_dd = float(drawdowns.max())

    calmar = annual_return / max(max_dd, 1e-8)

    # 从 trades 算胜率和盈亏比
    if trades:
        closed = [t for t in trades if "持仓中" not in str(t.get("exit", ""))]
        wins = [t for t in closed if t.get("return", 0) > 0]
        losses = [t for t in closed if t.get("return", 0) <= 0]

        win_rate = len(wins) / len(closed) if closed else 0
        avg_win = np.mean([t["return"] for t in wins]) if wins else 0
        avg_loss = abs(np.mean([t["return"] for t in losses])) if losses else 1
        profit_factor = (avg_win * len(wins)) / (avg_loss * len(losses)) if losses else float('inf')

        # 平均持仓天数
        avg_days = np.mean([t.get("days", 0) for t in closed]) if closed else 0
    else:
        win_rate = profit_factor = avg_days = 0

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "annual_volatility": annual_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "calmar_ratio": calmar,
        "total_trades": len(trades or []),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_hold_days": avg_days,
    }
