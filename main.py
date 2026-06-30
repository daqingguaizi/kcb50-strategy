#!/usr/bin/env python
"""科创50 trix 策略 — 一键全流程

Usage:
    python main.py           # 更新数据 + 算信号 + 回测 + 展示
    python main.py --no-update  # 跳过数据更新 (离线模式)
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# 确保当前目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import PARAMS, DATA_FILE, INITIAL_CAPITAL, STRATEGY_NAME, INDEX_NAME, ETF_CODE
from indicators import trix, ema
from strategy import generate_signals, get_trades
from backtest import compute_equity, compute_metrics


def main():
    import argparse
    parser = argparse.ArgumentParser(description=STRATEGY_NAME)
    parser.add_argument("--no-update", action="store_true", help="跳过数据更新")
    args = parser.parse_args()

    print()
    print("=" * 54)
    print(f"  {STRATEGY_NAME}")
    print(f"  参数: period={PARAMS['period']}, signal_period={PARAMS['signal_period']}")
    print("=" * 54)

    # ── Step 1: 更新数据 ──
    if not args.no_update:
        print("\n[1/4] 更新数据")
        from updater import update
        update(str(DATA_FILE))
    else:
        print("\n[1/4] 跳过数据更新")
        if not DATA_FILE.exists():
            print(f"  [错误] 数据文件不存在: {DATA_FILE}")
            sys.exit(1)

    # ── Step 2: 加载数据 + 算信号 ──
    print("\n[2/4] 计算 trix 信号...", end=" ", flush=True)
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    signals = generate_signals(df, **PARAMS)
    trades = get_trades(signals, df["close"])
    print(f"共 {len(trades)} 笔交易")

    # ── Step 3: 回测 ──
    print("[3/4] 跑回测...", end=" ", flush=True)
    equity = compute_equity(signals, df["close"], INITIAL_CAPITAL)
    metrics = compute_metrics(equity, trades)
    print("完成")

    # ── Step 4: 当前信号 ──
    print(f"\n[4/4] 当前状态\n")

    today = df.index[-1]
    current_signal = int(signals.iloc[-1])
    current_price = float(df["close"].iloc[-1])

    # 算持仓天数 & 入场价
    if current_signal == 1:
        # 找最近一次入场
        entry_idx = None
        for i in range(len(signals) - 1, -1, -1):
            if signals.iloc[i] == 0:
                entry_idx = i + 1
                break
        if entry_idx is None:
            entry_idx = 0

        entry_date = signals.index[entry_idx]
        entry_price = float(df["close"].iloc[entry_idx])
        hold_days = (today - entry_date).days
        pnl = (current_price / entry_price - 1)
    else:
        entry_date = "—"
        entry_price = "—"
        hold_days = "—"
        pnl = 0.0

    signal_text = "做多 (LONG)" if current_signal == 1 else "空仓 (CASH)"

    # ── 输出界面 ──
    print("╔" + "═" * 52 + "╗")
    print(f"║  {STRATEGY_NAME} — {today.strftime('%Y-%m-%d')}".ljust(53) + "║")
    print("╠" + "═" * 52 + "╣")
    print(f"║  当前信号:  {signal_text}".ljust(53) + "║")

    if current_signal == 1:
        print(f"║  持仓天数:  第 {hold_days} 天".ljust(53) + "║")
        print(f"║  入场日期:  {str(entry_date)[:10]}".ljust(53) + "║")
        print(f"║  入场价格:  {entry_price}".ljust(53) + "║")
        print(f"║  当前价格:  {current_price:.2f}".ljust(53) + "║")
        print(f"║  浮动盈亏:  {pnl:+.1%}".ljust(53) + "║")

    print("╠" + "═" * 52 + "╣")
    print(f"║  ── 策略统计 ──".ljust(53) + "║")
    print(f"║  历史胜率:  {metrics['win_rate']:.1%}    盈亏比: {metrics['profit_factor']:.2f}".ljust(53) + "║")
    print(f"║  累计收益:  {metrics['total_return']:+.1%}  最大回撤: {metrics['max_drawdown']:.1%}".ljust(53) + "║")
    print(f"║  年化收益:  {metrics['annual_return']:+.1%}   交易次数: {metrics['total_trades']}".ljust(53) + "║")
    print(f"║  Sharpe:    {metrics['sharpe_ratio']:.4f}      持仓均天: {metrics['avg_hold_days']:.0f}天".ljust(53) + "║")
    print("╚" + "═" * 52 + "╝")

    # ── 最近5笔交易 ──
    if trades:
        print(f"\n  最近 5 笔交易:")
        print(f"  {'入场':<12s} {'出场':<12s} {'收益':>8s} {'持仓':>6s}")
        print(f"  {'-'*42}")
        for t in trades[-5:]:
            entry = t["entry"][:10]
            exit_ = t["exit"][:10]
            ret = t["return"]
            days = t["days"]
            print(f"  {entry:<12s} {exit_:<12s} {ret:>+7.1%} {days:>5d}天")

    print()
    print(f"  ETF标的: {ETF_CODE} | 数据截止: {today.strftime('%Y-%m-%d')}")
    print(f"  下次运行: python main.py")


if __name__ == "__main__":
    main()
