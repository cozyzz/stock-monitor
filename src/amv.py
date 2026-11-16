# -*- coding: utf-8 -*-
"""amv.py — 0AMV 活跃市值近似版计算（用户提供的指南针近似公式）

VAR1 = SMA(AMOUNT,10,1) ≡ EMA(AMOUNT, alpha=0.1, adjust=False)   成交额平滑序列
红绿柱 = VAR1 vs REF(VAR1,1)
成本均线 Cx = DMA(SMA(VAR1, sma_n, 1), 换手率/threshold)
  SMA(X,1,1)=X 本身；换手率≈成交额/流通市值（小数）
"""
import pandas as pd
import numpy as np


def sma(x: pd.Series, n: int, m: int = 1) -> pd.Series:
    """通达信 SMA(X,N,M)=(M*X+(N-M)*prev)/N ≡ EMA(alpha=M/N, adjust=False)"""
    if n <= 1:
        return x.copy().astype(float)
    return x.astype(float).ewm(alpha=m / n, adjust=False).mean()


def dma(x: pd.Series, weight: pd.Series) -> pd.Series:
    """通达信 DMA(X,A)=A*X+(1-A)*DMA_prev，A 逐日变，clamp[0,1]"""
    a = weight.clip(0, 1.0).fillna(0.0).to_numpy(dtype=float)
    xv = x.to_numpy(dtype=float)
    out = np.empty(len(xv))
    out[0] = xv[0] if np.isfinite(xv[0]) else 0.0
    prev = out[0]
    for i in range(1, len(xv)):
        if np.isfinite(xv[i]) and np.isfinite(a[i]):
            prev = a[i] * xv[i] + (1 - a[i]) * prev
        out[i] = prev
    return pd.Series(out, index=x.index, dtype=float)


def calc_0amv(df: pd.DataFrame, amount_col="amount", turnover_col="turnover",
              params=None) -> pd.DataFrame:
    """输入: 日期索引 df，含 amount(成交额,元) + turnover(换手率,小数)
    输出: 追加 VAR1,VAR2,bar_color,C5,C13,C34,inf"""
    p = params or {
        "var1_alpha": 0.1,
        "cost_lines": [
            {"name": "C5", "sma_n": 3, "threshold": 0.02},
            {"name": "C13", "sma_n": 5, "threshold": 0.10},
            {"name": "C34", "sma_n": 8, "threshold": 0.18},
            {"name": "inf", "sma_n": 1, "threshold": 1.10},
        ],
    }
    amt = df[amount_col].astype(float)
    turn = df[turnover_col].astype(float)   # 已是小数（调用方负责转换）
    out = df.copy()
    out["VAR1"] = amt.ewm(alpha=p["var1_alpha"], adjust=False).mean()
    out["VAR2"] = out["VAR1"].shift(1)
    out["bar_color"] = np.where(out["VAR1"] > out["VAR2"], 1,
                          np.where(out["VAR1"] < out["VAR2"], -1, 0))
    for c in p["cost_lines"]:
        s = sma(out["VAR1"], c["sma_n"], 1)
        w = turn / c["threshold"]
        out[c["name"]] = dma(s, w)
    return out
