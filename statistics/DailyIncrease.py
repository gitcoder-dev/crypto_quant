import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time

def fetch_24h_tickers():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    response = requests.get(url)
    return response.json()

def filter_usdt_pairs(data):
    return [item for item in data if item['symbol'].endswith('USDT') and not item['symbol'].endswith('BUSD')]

def get_top_20_symbols():
    tickers = fetch_24h_tickers()
    usdt_pairs = filter_usdt_pairs(tickers)
    df = pd.DataFrame(usdt_pairs)
    df['quoteVolume'] = pd.to_numeric(df['quoteVolume'], errors='coerce')
    df = df.dropna().sort_values(by='quoteVolume', ascending=False).reset_index(drop=True)
    top_20 = df.head(20)
    return top_20['symbol'].tolist()

def fetch_historical_prices(symbol, interval='1d', limit=365):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'trades',
        'taker_base_vol', 'taker_quote_vol', 'ignore'
    ])
    df['close'] = pd.to_numeric(df['close'])
    return df[['timestamp', 'close']]

def calculate_annualized_return(prices_df):
    if len(prices_df) < 2:
        return None
    start_price = prices_df['close'].iloc[0]
    end_price = prices_df['close'].iloc[-1]
    days = len(prices_df)
    annualized_return = ((end_price / start_price) ** (365 / days) - 1) * 100
    return annualized_return

def main():
    print("🔍 获取前 20 币种...")
    top_symbols = get_top_20_symbols()

    annual_returns = {}
    for symbol in top_symbols:
        print(f"📈 获取 {symbol} 历史数据中...")
        try:
            df = fetch_historical_prices(symbol)
            annual_return = calculate_annualized_return(df)
            if annual_return is not None:
                annual_returns[symbol] = annual_return
        except Exception as e:
            print(f"❌ {symbol} 获取失败: {e}")
        time.sleep(0.5)  # Binance API 限速保护

    # 转为DataFrame并绘图
    result_df = pd.DataFrame(list(annual_returns.items()), columns=['Symbol', 'Annualized Return'])
    result_df = result_df.sort_values(by='Annualized Return', ascending=False)

    plt.figure(figsize=(12, 6))
    bars = plt.bar(result_df['Symbol'], result_df['Annualized Return'], color='skyblue')
    plt.xlabel("Symbol")
    plt.ylabel("Annualized Return (%)")
    plt.title("📊 Top 20 币种年化涨幅 (基于过去365日)")
    plt.xticks(rotation=45)
    plt.axhline(y=0, color='gray', linestyle='--')

    # 添加涨幅标签
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, yval, f'{yval:.1f}%', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
