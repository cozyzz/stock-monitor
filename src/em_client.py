# -*- coding: utf-8 -*-
"""em_client.py — 东财客户端(带UA限速重试,绕过AkShare裸请求被断连问题)

东财对频率敏感: AkShare用push2delay+裸请求会被RemoteDisconnected;
这里直调push2/push2his带浏览器UA+请求间隔≥3s+重试。
2026-11-13 验证时本机IP被东财API端点限流(push2/push2his全断,首页通),
限流恢复后本模块即可用。盘中每分钟1次低频不会触发。
"""
import time, requests
import pandas as pd
import config

_last_req = 0.0


def _wait():
    global _last_req
    dt = time.time() - _last_req
    if dt < config.EM_RATE_LIMIT_SEC:
        time.sleep(config.EM_RATE_LIMIT_SEC - dt)
    _last_req = time.time()


def _get(url, params):
    last = None
    for i in range(config.EM_MAX_RETRIES):
        _wait()
        try:
            r = requests.get(url, params=params, headers=config.EM_HEADERS, timeout=20)
            return r.json()
        except Exception as e:
            last = e
    raise last


def fetch_etf_spot(codes=None):
    """东财ETF实时列表。返回份额f38/成交额f6/规模f20/换手率f8等。
    codes=None返回全部，否则过滤"""
    params = {
        "pn": "1", "pz": "300", "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f12",
        "fs": "b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827",
        "fields": "f12,f14,f2,f3,f6,f8,f20,f21,f38,f297",
    }
    d = _get("https://push2.eastmoney.com/api/qt/clist/get", params)
    rows = d.get("data", {}).get("diff", []) or []
    df = pd.DataFrame(rows)
    if codes and len(df):
        df = df[df["f12"].isin(codes)]
    return df


def fetch_kline(code: str, lmt: int = 60, end: str = "20261113") -> pd.DataFrame:
    """东财日K(含成交额f6/换手率)。klt=101日K。
    klines格式: 日期,开,收,高,低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率(%)"""
    params = {
        "secid": config.em_secid(code), "klt": "101", "fqt": "1", "end": end, "lmt": str(lmt),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
    }
    d = _get("https://push2his.eastmoney.com/api/qt/stock/kline/get", params)
    kls = d.get("data", {}).get("klines", []) or []
    rows = [k.split(",") for k in kls]
    df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low",
                                     "volume", "amount", "amp", "pct", "chg", "turnover"])
    for c in ["open", "close", "high", "low", "volume", "amount", "turnover"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["turnover"] = df["turnover"] / 100.0   # %→小数
    return df


def fetch_index_kline(index_code: str, lmt: int = 60, end: str = "20261113") -> pd.DataFrame:
    """指数历史K线(含成交额)。指数secid: 沪1.000001 深0.399001"""
    secid = f"1.{index_code}" if index_code.startswith("000") else f"0.{index_code}"
    return fetch_kline_raw(secid, lmt, end)


def fetch_kline_raw(secid: str, lmt: int = 60, end: str = "20261113") -> pd.DataFrame:
    params = {
        "secid": secid, "klt": "101", "fqt": "1", "end": end, "lmt": str(lmt),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
    }
    d = _get("https://push2his.eastmoney.com/api/qt/stock/kline/get", params)
    kls = d.get("data", {}).get("klines", []) or []
    rows = [k.split(",") for k in kls]
    df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low",
                                     "volume", "amount", "amp", "pct", "chg", "turnover"])
    for c in ["open", "close", "high", "low", "volume", "amount", "turnover"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["turnover"] = df["turnover"] / 100.0
    return df
