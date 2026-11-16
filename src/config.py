# -*- coding: utf-8 -*-
"""
config.py — 监控标的与0AMV参数配置（用户自维护）
"""
import os, json

# ==================== 重点宽基ETF清单（看国家队主战场）====================
# 每个指数下挂多只ETF，监控时全部跟踪份额变化，取规模最大者为代表显示
# 代码市场前缀：5=沪 1=深，东财secid=市场.代码（1.沪 0.深，注意东财深市前缀是0）
KEY_ETFS = {
    "沪深300":   ["510300", "159919", "510310", "510350"],
    "上证50":    ["510050", "510800"],
    "中证500":   ["510500", "159922"],
    "中证1000":  ["512100", "560010", "159845"],
    "中证A500":  ["512050", "159338", "562360"],
    "创业板":    ["159915"],
}

# ==================== 0AMV 近似公式参数（用户提供，非指南针原版）====================
# VAR1 = SMA(AMOUNT,10,1) ≡ EMA(AMOUNT, alpha=0.1, adjust=False)
# 红绿柱: VAR1 vs REF(VAR1,1)
# 成本均线 Cx = DMA(SMA(VAR1, sma_n, 1), 换手率/threshold)
#   SMA(X,1,1) = X 本身（∞线用 VAR1 本身做 DMA）
#   换手率 ≈ 成交额/流通市值
AMV_PARAMS = {
    "var1_alpha": 0.1,                 # SMA(AMOUNT,10,1) → EMA alpha=1/10
    "cost_lines": [
        {"name": "C5",  "sma_n": 3, "threshold": 0.02},   # 换手率门槛2%，最快
        {"name": "C13", "sma_n": 5, "threshold": 0.10},   # 10%
        {"name": "C34", "sma_n": 8, "threshold": 0.18},   # 18%
        {"name": "inf", "sma_n": 1, "threshold": 1.10},   # 110%，最慢（≈长线成本）
    ],
}

# ==================== 全市场指数（0AMV历史成交额=沪+深）====================
MARKET_INDEX = {"sh": "sh000001", "sz": "sz399107"}   # 深证综指（已补测确认）

# ==================== 取数限速（东财对频率敏感）====================
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
EM_RATE_LIMIT_SEC = 3.0   # 东财请求最小间隔
EM_MAX_RETRIES = 4

# ==================== 数据存储 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_CSV = os.path.join(DATA_DIR, "0amv_history.csv")     # 0AMV逐日序列
ETF_SNAP_CSV = os.path.join(DATA_DIR, "etf_snap.csv")       # ETF份额逐日快照

# 标的清单扁平化（供取数遍历）
ALL_ETF_CODES = sorted({c for codes in KEY_ETFS.values() for c in codes})


def em_secid(code: str) -> str:
    """东财 secid：沪市(5开头/6开头)→1.代码，深市(1开头/0开头/3开头)→0.代码"""
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    return f"0.{code}"
