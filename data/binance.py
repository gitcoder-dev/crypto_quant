from binance.client import Client
import datetime
import pandas as pd

# 初始化币安客户端
client = Client()

# 获取历史k线数据
def get_binance_btc_data(symbol='BTCUSDT', interval='1d', lookback_days=600):
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=lookback_days)

    klines = client.get_historical_klines(
        symbol,
        interval,
        start_str=start_time.strftime("%d %b %Y %H:%M:%S"),
        end_str=end_time.strftime("%d %b %Y %H:%M:%S")
    )

    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

    return df

df = get_binance_btc_data()

# backtrader 数据接口
class PandasData(bt.feeds.PandasData):
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', -1),
    )