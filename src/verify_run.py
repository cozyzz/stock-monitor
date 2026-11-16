# -*- coding: utf-8 -*-
"""verify_run.py — 数据层验证：近30日0AMV + 今日全市场实时 + 重点宽基ETF份额
跑法: py -3.12 -I e:/qingyuan-smartcity/stock-monitor/src/verify_run.py
"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import config, amv, sina_client, em_client

pd.set_option('display.width', 220)
pd.set_option('display.unicode.east_asian_width', True)

# ---------- 1. 0AMV 历史（上证综指 沪市，近40日）----------
print("=" * 70)
print("[1] 0AMV 历史 — 上证综指(沪市) 近40日")
print("=" * 70)
try:
    h = sina_client.index_history("sh000001", "20260920", "20261112")
    h = h.dropna(subset=["amount"]).set_index("date").sort_index()
    res = amv.calc_0amv(h, amount_col="amount", turnover_col="turnover", params=config.AMV_PARAMS)
    show = res[["amount", "VAR1", "bar_color", "C5", "C13", "C34", "inf"]].copy()
    for c in ["amount", "VAR1", "C5", "C13", "C34", "inf"]:
        show[c] = (show[c] / 1e8).round(1)   # 元→亿
    show["bar"] = show["bar_color"].map({1: "红(升温)", -1: "绿(降温)", 0: "-"})
    print(show.tail(20).to_string())
    print(f"\n最新一日: 沪市成交额={h['amount'].iloc[-1]/1e8:.0f}亿 VAR1={res['VAR1'].iloc[-1]/1e8:.1f}亿 {show['bar'].iloc[-1]}")
except Exception:
    traceback.print_exc()

# ---------- 2. 今日全市场实时（新浪全A聚合，含深市）----------
print("\n" + "=" * 70)
print("[2] 今日全市场实时 — 新浪全A聚合(含深市) 遍历~70页")
print("=" * 70)
try:
    m = sina_client.market_realtime_summary()
    print(f"股票数: {m['n_stocks']}")
    print(f"全市场总成交额: {m['total_amount']/1e8:.0f} 亿元")
    print(f"全市场总流通市值: {m['total_nmc']/1e8:.0f} 亿元")
    print(f"全市场换手率: {m['turnover']*100:.3f}%")
except Exception:
    traceback.print_exc()

# ---------- 2.5 活跃市值 = 全市场近10日累计成交额(口径:≈15万亿) ----------
print("\n" + "=" * 70)
print("[2.5] 活跃市值 — 全市场近10日累计成交额")
print("=" * 70)
try:
    import active_value
    av = active_value.active_market_value(days=10, end_date="20261112")
    print(f"近{av['days']}日活跃市值: {av['active_value']/1e8:.0f} 亿元 = {av['active_value']/1e12:.2f} 万亿元")
    print(f"  沪市近10日成交额: {av['sh_amount_nd']/1e8:.0f}亿  全市场系数: {av['coef']:.2f} ({av['coef_src']})")
    d = av["detail"].tail(10).copy()
    d["成交额(亿)"] = (d["amount"] / 1e8).round(0)
    print(d[["date", "成交额(亿)"]].to_string(index=False))
except Exception:
    traceback.print_exc()

# ---------- 3. 重点宽基ETF 份额（东财，限流中可能失败）----------
print("\n" + "=" * 70)
print("[3] 重点宽基ETF 份额/成交额 — 东财(限流中可能失败,恢复即用)")
print("=" * 70)
try:
    df = em_client.fetch_etf_spot(config.ALL_ETF_CODES)
    if len(df):
        cols = [c for c in ["f12", "f14", "f2", "f3", "f6", "f8", "f20", "f38", "f297"] if c in df.columns]
        print(df[cols].to_string(index=False))
    else:
        print("返回空")
except Exception as e:
    print(f"东财取数失败(预期,限流中): {type(e).__name__}: {str(e)[:120]}")

print("\n=== verify_run 完成 ===")
