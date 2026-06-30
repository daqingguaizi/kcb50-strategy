"""数据更新 — akshare 增量拉取科创50日线"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

try:
    import akshare as ak
except ImportError:
    print("[错误] 请先安装 akshare: pip install akshare")
    sys.exit(1)


def update(csv_path: str = None):
    """增量更新科创50日线数据"""
    if csv_path is None:
        csv_path = Path(__file__).parent / "data" / "000688.csv"
    csv_path = Path(csv_path)

    print("  正在拉取科创50最新数据...", end=" ", flush=True)

    try:
        df_new = ak.stock_zh_index_daily(symbol="sh000688")
        df_new.columns = [c.lower() for c in df_new.columns]
        df_new["date"] = pd.to_datetime(df_new["date"])
    except Exception as e:
        print(f"\n  [错误] 拉取失败: {e}")
        return csv_path

    if csv_path.exists():
        df_old = pd.read_csv(csv_path, encoding="utf-8-sig")
        df_old["date"] = pd.to_datetime(df_old["date"])
        last_date = df_old["date"].max()
        new_rows = df_new[df_new["date"] > last_date]

        if len(new_rows) > 0:
            df_merged = pd.concat([df_old, new_rows], ignore_index=True)
            df_merged = df_merged.drop_duplicates(subset=["date"], keep="last")
            df_merged = df_merged.sort_values("date", ascending=True)
            df_merged.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"新增 {len(new_rows)} 行  ({new_rows['date'].min().date()} ~ {new_rows['date'].max().date()})")
        else:
            print(f"已是最新 (最后: {last_date.date()})")
    else:
        df_new = df_new.sort_values("date", ascending=True)
        df_new.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"首次下载 {len(df_new)} 行")

    return csv_path


if __name__ == "__main__":
    update()
