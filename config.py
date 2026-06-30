"""科创50 trix 策略 — 配置"""

from pathlib import Path

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "000688.csv"

# 最优参数 (超大规模寻优 OOS 验证)
PARAMS = {
    "period": 9,
    "signal_period": 17,
}

# 策略名称
STRATEGY_NAME = "科创50 trix策略"
INDEX_NAME = "科创50 (000688)"
ETF_CODE = "588000"  # 科创50ETF

# 初始资金
INITIAL_CAPITAL = 1_000_000
