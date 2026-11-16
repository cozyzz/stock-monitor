# -*- coding: utf-8 -*-
"""sina_client.py — 新浪源取数（全A实时聚合 + 指数历史）

新浪全A原始接口含全字段(amount成交额/nmc流通市值/turnoverratio换手率)，
AkShare封装版丢弃了nmc/turnoverratio，这里直调原始接口保留。
单位: amount=元, nmc=万元, turnoverratio=小数(0.05=5%)
"""
import time, requests
import pandas as pd
import akshare as ak
from akshare.utils import demjson
from akshare.stock.cons import zh_sina_a_stock_url, zh_sina_a_stock_payload
from akshare.stock.stock_zh_a_sina import _get_zh_a_page_count


def fetch_all_a_realtime(sleep=0.05, max_pages=None):
    """遍历新浪全A原始接口所有页，返回全字段DataFrame"""
    pages = max_pages or _get_zh_a_page_count()
    rows = []
    for p in range(1, pages + 1):
        payload = dict(zh_sina_a_stock_payload)
        payload["page"] = str(p)
        try:
            r = requests.get(zh_sina_a_stock_url, params=payload, timeout=20)
            rows.extend(demjson.decode(r.text))
        except Exception as e:
            print(f"  page {p} 失败: {e}")
        time.sleep(sleep)
    df = pd.DataFrame(rows)
    for c in ["trade", "amount", "mktcap", "nmc", "turnoverratio", "volume", "changepercent"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def market_realtime_summary(sleep=0.05):
    """全A实时聚合：总成交额/总流通市值/换手率(小数) + 分市场成交额(沪/深/北)"""
    df = fetch_all_a_realtime(sleep=sleep)
    df["market"] = df["symbol"].astype(str).str[:2]          # sh / sz / bj
    g = df.groupby("market")["amount"].sum()
    total_amount = float(df["amount"].sum())
    total_nmc = float(df["nmc"].sum()) * 1e4                  # 万元→元
    turnover = total_amount / total_nmc if total_nmc else 0.0
    return {
        "n_stocks": len(df),
        "total_amount": total_amount,
        "total_nmc": total_nmc,
        "turnover": turnover,
        "sh_amount": float(g.get("sh", 0)),
        "sz_amount": float(g.get("sz", 0)),
        "bj_amount": float(g.get("bj", 0)),
    }


def index_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """指数历史 开/高/低/收/成交额/换手率（新浪 stock_zh_a_daily）。
    注: 深市指数该接口报错，目前仅上证综指 sh000001 可用；
        深市历史成交额等东财恢复后由 em_client.fetch_kline 补全。"""
    d = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date, end_date=end_date, adjust="")
    for c in ["open", "high", "low", "close", "amount"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["turnover"] = pd.to_numeric(d["turnover"], errors="coerce") / 100.0   # %→小数
    return d[["date", "open", "high", "low", "close", "amount", "turnover"]]
