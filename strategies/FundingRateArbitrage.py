import backtrader as bt
import ccxt
import pandas as pd
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)

class FundingRateArbitrage(bt.Strategy):
    # 策略参数
    params = (
        ('funding_rate_threshold', 0.02),  # 资金费率差异的阈值
        ('commission_rate', 0.01),         # 交易佣金
    )

    def __init__(self):
        # 存储两个市场的资金费率
        self.funding_rate_exchange_1 = self.datas[0].close
        self.funding_rate_exchange_2 = self.datas[1].close

    def next(self):
        # 获取两个市场的资金费率
        fr1 = self.funding_rate_exchange_1[0]  # 第一个市场的资金费率
        fr2 = self.funding_rate_exchange_2[0]  # 第二个市场的资金费率

        # 如果资金费率差异大于阈值，则执行套利操作
        if abs(fr1 - fr2) > self.params.funding_rate_threshold:
            if fr1 > fr2:
                # 假设资金费率较高的市场为卖出市场，较低的为买入市场
                self.sell(data=self.datas[0], size=1)
                self.buy(data=self.datas[1], size=1)
                logging.info(f"Arbitrage opportunity: Sell on exchange 1, Buy on exchange 2")
            else:
                self.buy(data=self.datas[0], size=1)
                self.sell(data=self.datas[1], size=1)
                logging.info(f"Arbitrage opportunity: Buy on exchange 1, Sell on exchange 2")

    def stop(self):
        # 输出策略回测结果
        logging.info(f"Final portfolio value: {self.broker.getvalue()}")


# 数据加载
def fetch_funding_rate_data(exchange_name, symbol, start_date, end_date):
    """
    Fetch funding rate history from a specific exchange and symbol.
    This is a simplified version, you'd likely need to get real data from your API.
    """
    exchange = getattr(ccxt, exchange_name)()
    funding_history = exchange.fetch_funding_rate_history(symbol)
    timestamps = [datetime.utcfromtimestamp(f['timestamp'] / 1000) for f in funding_history]
    rates = [f['fundingRate'] * 100 for f in funding_history]  # 百分比形式

    # 将数据转换为Pandas DataFrame
    df = pd.DataFrame({'timestamp': timestamps, 'funding_rate': rates})
    df.set_index('timestamp', inplace=True)

    # 过滤日期范围
    df = df.loc[start_date:end_date]

    return df

# 读取资金费率数据（从真实交易所拉取或是本地数据）
df1 = fetch_funding_rate_data('binance', 'BTC/USDT', '2023-01-01', '2023-01-30')
df2 = fetch_funding_rate_data('bybit', 'BTC/USDT', '2023-01-01', '2023-01-30')

# 将数据转换为Backtrader数据格式
class PandasData1(bt.feeds.PandasData):
    lines = ('funding_rate',)
    params = (
        ('datetime', None),  # 默认从DataFrame的index读取时间
        ('funding_rate', 'funding_rate'),
    )

class PandasData2(bt.feeds.PandasData):
    lines = ('funding_rate',)
    params = (
        ('datetime', None),
        ('funding_rate', 'funding_rate'),
    )

# 将数据加载到Backtrader中
data1 = PandasData1(dataname=df1)
data2 = PandasData2(dataname=df2)

# 设置回测引擎
cerebro = bt.Cerebro()
cerebro.adddata(data1)
cerebro.adddata(data2)
cerebro.addstrategy(FundingRateArbitrage)

# 设置初始资金和佣金
cerebro.broker.set_cash(100000)
cerebro.broker.set_commission(commission=0.001)

# 设置回测时间范围
cerebro.addobserver(bt.observers.Value)
cerebro.addobserver(bt.observers.DrawDown)

# 运行回测
cerebro.run()

# 输出最终结果
print(f"Final Portfolio Value: {cerebro.broker.getvalue()}")
