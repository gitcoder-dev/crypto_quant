# 获取每日BTC涨幅，市值前20的代币平均涨幅和市值前50代币平均涨幅
import requests
from datetime import datetime
import time

BINANCE_API_BASE = "https://api.binance.com"
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"


def get_binance_price_change(symbol: str):
    """获取币安24小时价格变动数据"""
    url = f"{BINANCE_API_BASE}/api/v3/ticker/24hr?symbol={symbol}"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        return float(data["priceChangePercent"])
    else:
        return None


def get_top_market_cap_symbols(limit=50):
    """获取CoinGecko市值前N的代币symbol（转换为币安交易对格式）"""
    url = f"{COINGECKO_API_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": False,
    }
    resp = requests.get(url, params=params)
    result = []
    if resp.status_code == 200:
        for coin in resp.json():
            symbol = coin["symbol"].upper()
            if symbol == "USDT":
                continue
            result.append(symbol + "USDT")
    return result


def get_average_change(symbols):
    """计算给定币种列表的平均涨幅"""
    changes = []
    for symbol in symbols:
        try:
            change = get_binance_price_change(symbol)
            if change is not None:
                changes.append(change)
            time.sleep(0.1)  # 避免请求过快被限制
        except Exception as e:
            print(f"跳过 {symbol}，错误: {e}")
    if changes:
        return sum(changes) / len(changes)
    return 0


def main():
    print(f"\n🕒 当前时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

    btc_change = get_binance_price_change("BTCUSDT")
    if btc_change is not None:
        print(f"\n📈 今日 BTC 涨幅：{btc_change:.2f}%")
    else:
        print("无法获取 BTC 涨幅")

    symbols_top_50 = get_top_market_cap_symbols(limit=50)
    symbols_top_20 = symbols_top_50[:20]

    avg_change_20 = get_average_change(symbols_top_20)
    print(f"\n📊 市值前 20 代币今日平均涨幅：{avg_change_20:.2f}%")

    avg_change_50 = get_average_change(symbols_top_50)
    print(f"\n📊 市值前 50 代币今日平均涨幅：{avg_change_50:.2f}%")


if __name__ == "__main__":
    main()
