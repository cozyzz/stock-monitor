# -*- coding: utf-8 -*-
"""active_value.py — 活跃市值 = 全市场(沪+深+北)近N日累计成交额

口径(用户2026-11-13确认): 活跃市值≈15万亿 = 近10日全市场累计成交额
  - 沪市历史成交额: stock_zh_a_daily sh000001 (精确,有amount)
  - 全市场系数: 今日(全市场成交额/沪市成交额)，新浪全A聚合分市场算
    沪市长期约占全市场55%，系数≈1.82；今日动态校准更准
  - 东财push2his恢复后可改用深市amount做精确沪+深累计(替换系数法)
"""
import pandas as pd
import sina_client

FALLBACK_COEF = 1.82   # 沪市约占全市场55% → 1/0.55


def active_market_value(days=10, end_date="20261112", start_offset=40, today_ref=False):
    """全市场近days日累计成交额(活跃市值,元)
    today_ref=True时额外拉今日全A聚合算参考系数(慢~20s,盘中占比不稳,默认关闭)"""
    start = (pd.to_datetime(end_date) - pd.Timedelta(days=start_offset)).strftime("%Y%m%d")
    sh = sina_client.index_history("sh000001", start, end_date)
    sh = sh.dropna(subset=["amount"]).sort_values("date").reset_index(drop=True)
    sh_recent = sh.tail(days)
    sh_total = float(sh_recent["amount"].sum())

    # 系数: 默认固定(沪市长期约占全市场55%); 今日盘中占比不稳+易缺页,仅作参考
    coef = FALLBACK_COEF
    coef_src = f"固定{FALLBACK_COEF}(沪市长期占比~55%)"
    if today_ref:
        try:
            m = sina_client.market_realtime_summary()
            sh_today = m.get("sh_amount", 0)
            tc = m["total_amount"] / sh_today if sh_today else None
            if tc:
                coef_src += f" | 今日参考{tc:.2f}(全{m['total_amount']/1e8:.0f}/沪{sh_today/1e8:.0f}亿,盘中不稳)"
        except Exception as e:
            coef_src += f" | 今日取数失败:{type(e).__name__}"

    total = sh_total * coef
    return {
        "active_value": total,            # 活跃市值(元)
        "sh_amount_nd": sh_total,          # 沪市近N日成交额(元)
        "coef": coef,
        "coef_src": coef_src,
        "days": len(sh_recent),
        "detail": sh_recent[["date", "amount"]].copy(),
    }
