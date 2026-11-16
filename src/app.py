# -*- coding: utf-8 -*-
"""app.py — A股活跃市值+0AMV+宽基ETF监控看板(标准库,零依赖)
跑法: py -3.12 -I app.py  →  http://localhost:8766
"""
import json, os, sys, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import config, amv, sina_client, active_value, em_client

HOST, PORT = "127.0.0.1", 8766
BASE = os.path.dirname(os.path.abspath(__file__))
_CACHE = {}


def cached(key, fn, ttl):
    now = time.time()
    if key in _CACHE and now - _CACHE[key][1] < ttl:
        return _CACHE[key][0]
    try:
        val = fn()
    except Exception as e:
        val = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    _CACHE[key] = (val, now)
    return val


def _today():
    return datetime.now().strftime("%Y%m%d")


def api_0amv():
    end = _today()
    start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
    h = sina_client.index_history("sh000001", start, end)
    h = h.dropna(subset=["amount"]).copy()
    h["date"] = pd.to_datetime(h["date"])
    h = h.set_index("date").sort_index()
    res = amv.calc_0amv(h, amount_col="amount", turnover_col="turnover", params=config.AMV_PARAMS)
    res = res.tail(45)
    dates = res.index.strftime("%m-%d").tolist()

    def r(c):
        return [None if pd.isna(x) else round(float(x), 1) for x in res[c]]

    last = res.iloc[-1]
    bar = int(last["bar_color"])
    return {
        "dates": dates,
        "amount": r("amount"), "VAR1": r("VAR1"),
        "C5": r("C5"), "C13": r("C13"), "C34": r("C34"), "inf": r("inf"),
        "bar": [int(x) for x in res["bar_color"]],
        "latest": {
            "date": res.index[-1].strftime("%Y-%m-%d"),
            "amount": round(float(last["amount"]) / 1e8, 0),
            "VAR1": round(float(last["VAR1"]) / 1e8, 1),
            "bar": "红(升温)" if bar > 0 else ("绿(降温)" if bar < 0 else "—"),
        },
    }


AMV_FACTOR = 1.84   # 沪市→全市场因子(0AMV口径, 8个参考点校准均值1.839; std=0.05,放量日~1.90缩量日~1.78)


def api_active_value():
    end = _today()
    start = (datetime.now() - timedelta(days=420)).strftime("%Y%m%d")   # ~280交易日, 取最近250根覆盖一整年
    sh = sina_client.index_history("sh000001", start, end)
    sh = sh.dropna(subset=["amount", "close"]).sort_values("date").reset_index(drop=True).copy()
    sh["date"] = pd.to_datetime(sh["date"])
    # 0AMV活跃市值(收盘): VAR1=EMA(AMOUNT,0.1)/1e7 ×因子推全市场, 单位万亿
    sh["VAR1"] = sh["amount"].astype(float).ewm(alpha=0.1, adjust=False).mean() / 1e7
    sh["av"] = (sh["VAR1"] * AMV_FACTOR / 1e4).round(2)            # 收盘(万亿)
    # 盘中开高低: 0AMV盘中波动主因=流通市值随股价波动, 用指数当日开高低/收 套到活跃市值收盘
    sh["av_open"] = (sh["av"] * sh["open"] / sh["close"]).round(2)
    sh["av_high"] = (sh["av"] * sh["high"] / sh["close"]).round(2)
    sh["av_low"] = (sh["av"] * sh["low"] / sh["close"]).round(2)
    sh["ma10"] = sh["av"].rolling(10).mean().round(2)
    recent = sh.tail(250)
    last = recent.iloc[-1]
    ohlc = [[float(o), float(c), float(lo), float(hi)]
            for o, c, lo, hi in zip(recent["av_open"], recent["av"], recent["av_low"], recent["av_high"])]
    return {
        "value_wy": float(last["av"]),
        "factor": AMV_FACTOR,
        "last_date": recent["date"].iloc[-1].strftime("%Y-%m-%d"),
        "trend_dates": recent["date"].dt.strftime("%Y-%m-%d").tolist(),
        "ohlc": ohlc,
        "ma10": [None if pd.isna(x) else float(x) for x in recent["ma10"].tolist()],
        "y_min": float(recent["av_low"].min()),
        "y_max": float(recent["av_high"].max()),
    }


def api_realtime():
    m = sina_client.market_realtime_summary()
    return {
        "n_stocks": m["n_stocks"],
        "total_amount": round(m["total_amount"] / 1e8, 0),
        "total_nmc": round(m["total_nmc"] / 1e8, 0),
        "turnover": round(m["turnover"] * 100, 3),
        "sh_amount": round(m["sh_amount"] / 1e8, 0),
        "sz_amount": round(m["sz_amount"] / 1e8, 0),
        "bj_amount": round(m["bj_amount"] / 1e8, 0),
        "time": datetime.now().strftime("%H:%M:%S"),
    }


def api_etf():
    try:
        df = em_client.fetch_etf_spot(config.ALL_ETF_CODES)
        if not len(df):
            return {"available": False, "msg": "东财限流中,份额暂不可用(恢复即自动填充)", "data": []}
        df = df.copy()
        for c in ["f2", "f3", "f6", "f8", "f20", "f38"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        data = []
        for _, x in df.iterrows():
            data.append({
                "code": x.get("f12"), "name": x.get("f14"),
                "price": (None if pd.isna(x.get("f2")) else round(float(x["f2"]), 3)),
                "pct": (None if pd.isna(x.get("f3")) else round(float(x["f3"]), 2)),
                "amount": (None if pd.isna(x.get("f6")) else float(x["f6"])),
                "turnover": (None if pd.isna(x.get("f8")) else round(float(x["f8"]), 2)),
                "scale": (None if pd.isna(x.get("f20")) else float(x["f20"])),
                "share": (None if pd.isna(x.get("f38")) else float(x["f38"])),
                "date": x.get("f297"),
            })
        return {"available": True, "data": data}
    except Exception as e:
        return {"available": False, "msg": f"东财取数失败:{type(e).__name__}", "data": []}


ROUTES = {
    "/api/0amv": (api_0amv, 300),
    "/api/active_value": (api_active_value, 300),
    "/api/realtime": (api_realtime, 300),
    "/api/etf": (api_etf, 60),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, b, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _json(self, obj):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            p = os.path.join(BASE, "static", "index.html")
            if os.path.exists(p):
                self._send(open(p, "rb").read(), "text/html; charset=utf-8")
            else:
                self._json({"error": "index.html not found"})
            return
        if self.path in ROUTES:
            fn, ttl = ROUTES[self.path]
            self._json(cached(self.path, fn, ttl))
            return
        self._json({"error": "not found", "path": self.path})


def main():
    print(f"看板启动 → http://localhost:{PORT}")
    print("Ctrl+C 停止")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
