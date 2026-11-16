# -*- coding: utf8 -*-
import os
import requests
import time
from datetime import datetime

BARK_KEY = os.environ.get("BARK_KEY")

# ===================== 【在这里维护你的股票列表】=====================
# market: CN=A股, US=美股；buy_price：补仓预警价格，跌到该价位推送提醒
# A股代码直接6位；美股代码，新浪接口美股需要加前缀，如AAPL=AAPL.O
stock_list = [
    {"market":"CN","code":"600418","name":"江淮汽车","buy_price":23},
    {"market":"US","code":"AAPL.O","name":"苹果","buy_price":180},
    {"market":"US","code":"NVDA.O","name":"英伟达","buy_price":280},
    {"market":"US","code":"PATH.O","name":"Uipath","buy_price":12}
]
# =====================================================================

def send_bark(title, body):
    """调用Bark推送iOS系统通知"""
    url = f"https://api.day.app/{BARK_KEY}/{title}/{body}"
    try:
        requests.get(url, timeout=8)
    except Exception as e:
        print(f"Bark推送异常: {e}")

def get_cn_price(code):
    """获取A股实时价格 新浪接口"""
    url = f"https://hq.sinajs.cn/list={code}"
    headers = {"Referer": "https://finance.sina.com.cn"}
    resp = requests.get(url, headers=headers, timeout=8)
    resp.encoding = "gbk"
    data = resp.text.split(",")
    if len(data) > 3:
        return float(data[3])
    return None

def get_us_price(code):
    """获取美股实时价格 新浪接口，美股代码需要 .O 后缀"""
    url = f"https://hq.sinajs.cn/list={code}"
    headers = {"Referer": "https://finance.sina.com.cn"}
    resp = requests.get(url, headers=headers, timeout=8)
    resp.encoding = "gbk"
    data = resp.text.split(",")
    if len(data) > 1:
        return float(data[1])
    return None

def is_cn_trade_time(now:datetime):
    """A股交易时段判断：9:30~11:30，13:00~15:00"""
    h = now.hour
    m = now.minute
    if (9 <= h <12) or (13 <= h <15):
        if not ((h ==11 and m>30) or (h ==14 and m>59)):
            return True
    return False

def is_us_trade_time(now:datetime):
    """美股夏令时：北京时间 21:30 ~ 次日04:00"""
    h = now.hour
    if (h >=21) or (h <4):
        if h ==21 and now.minute <30:
            return False
        return True
    return False

def main_handler(event, context):
    now = datetime.now()
    print(f"本次执行时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    for stock in stock_list:
        time.sleep(0.3)
        market = stock["market"]
        code = stock["code"]
        name = stock["name"]
        buy_price = stock["buy_price"]

        if market == "CN":
            if not is_cn_trade_time(now):
                print(f"{name} 非A股交易时段，跳过")
                continue
            current_price = get_cn_price(code)
        elif market == "US":
            if not is_us_trade_time(now):
                print(f"{name} 非美股交易时段，跳过")
                continue
            current_price = get_us_price(code)
        else:
            continue

        if current_price is None:
            print(f"{name} 获取行情失败")
            continue
        print(f"{name} 当前价:{current_price},补仓预警线:{buy_price}")

        # 补仓判断：价格跌到预警线及以下，推送提醒；同一自然日只会推送一次
        if current_price <= buy_price:
            alert_msg = f"{name} 到达补仓预警线 {buy_price}\n当前价：{current_price}"
            send_bark(f"📉补仓提醒", alert_msg)
            print(f"ALERT_SENT_{market}_{code}_{now.date()}")

    return {"msg":"本轮监控执行完成"}

