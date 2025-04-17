#该策略回测效果非常差，需您进行优化或结合其他因子共同使用
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import backtrader as bt
import pandas as pd
from binance.client import Client
import datetime
import seaborn as sns

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 处理变量为none
def format_float(value, digits=2):
    return f"{value:.{digits}f}" if value is not None else "N/A"

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

# 布林带策略
class BBStrategy(bt.Strategy):
    params = (
        ('bb_period', 20),  # 布林带周期
        ('bb_dev', 2),  # 布林带标准差
        ('rsi_period', 14),  # RSI周期
        ('rsi_overbought', 70),  # 超买阈值
        ('rsi_oversold', 30),  # 超卖阈值
    )

    def __init__(self):
        self.bollinger = bt.indicators.BollingerBands(self.data.close, period=self.p.bb_period, devfactor=self.p.bb_dev)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)

    def next(self):
        if not self.position:  # 如果没有持仓
            # 按照布林带突破策略
            if self.data.close[0] > self.bollinger.lines.top[0]:  # 当前价格突破上轨
                if self.rsi[0] < self.p.rsi_oversold:  # 超卖区域，潜在反转
                    self.buy()  # 做多

            elif self.data.close[0] < self.bollinger.lines.bot[0]:  # 当前价格突破下轨
                if self.rsi[0] > self.p.rsi_overbought:  # 超买区域，潜在反转
                    self.sell()  # 做空

        else:
            # 平仓逻辑：价格回到布林带中轨附近
            if self.position.size > 0:  # 多头持仓
                if self.data.close[0] < self.bollinger.lines.mid[0]:  # 价格回落至中轨
                    self.close()  # 平多单

            elif self.position.size < 0:  # 空头持仓
                if self.data.close[0] > self.bollinger.lines.mid[0]:  # 价格回升至中轨
                    self.close()  # 平空单

# 设置Backtrader
def run_backtest_and_plot(interval, bb_period, bb_dev, rsi_period, plot=False):
    df = get_binance_btc_data(interval=interval)
    data = PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.0008)
    cerebro.adddata(data)

    cerebro.addstrategy(
        BBStrategy,
        bb_period=bb_period,
        bb_dev=bb_dev,
        rsi_period=rsi_period
    )

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    results = cerebro.run()
    strat = results[0]

    # 获取分析结果
    sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', None)
    returns = strat.analyzers.returns.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()

    rtot = returns.get('rtot', None)
    annual = returns.get('rnorm', None)
    average = returns.get('ravg', None)
    maxdd = drawdown.get('max', {}).get('drawdown', None)

    # 输出分析结果
    print(f"[{interval}] bb_period={bb_period}, bb_dev={bb_dev}, rsi={rsi_period} | "
          f"Sharpe: {format_float(sharpe)}, "
          f"Return: {format_float(rtot * 100 if rtot is not None else None)}%, "
          f"MaxDD: {format_float(maxdd)}%, "
          f"Annual: {format_float(annual * 100 if annual is not None else None)}%, "
          f"Avg: {format_float(average * 100 if average is not None else None)}%")

    # 绘图
    if plot:
        cerebro.plot(
            style='candlestick',
            barup='green',
            bardown='red',
            grid=True,
            volume=True,
            figsize=(18, 9),
            dpi=120
        )

    return {
        'interval': interval,
        'bb_period': bb_period,
        'bb_dev': bb_dev,
        'rsi_period': rsi_period,
        'sharpe': sharpe,
        'return': rtot,
        'maxdd': maxdd,
        'annual': annual,
        'average': average,
    }

def main():
    best_result = None
    best_annual = -float('inf')
    best_sharpe_result = None
    best_sharpe = -float('inf')
    all_results = []

    intervals = ['12h','1d']
    bb_period_range = range(15, 30, 5)
    bb_dev_range = [1.5, 2, 2.5]
    rsi_period_range = [7, 18, 4]

    print("🔍 正在进行参数优化...\n")

    for interval in intervals:
        for bb_period in bb_period_range:
            for bb_dev in bb_dev_range:
                for rsi_period in rsi_period_range:
                    result = run_backtest_and_plot(interval, bb_period, bb_dev, rsi_period, plot=False)
                    if result:
                        all_results.append(result)

                        if result['annual'] is not None and result['annual'] > best_annual:
                            best_annual = result['annual']
                            best_result = result
                        if result['sharpe'] is not None and result['sharpe'] > best_sharpe:
                            best_sharpe = result['sharpe']
                            best_sharpe_result = result

    # 最佳年化
    print("\n🏆 最佳年化参数组合:")
    print(f"周期: {best_result['interval']}, bb_period={best_result['bb_period']}, bb_dev={best_result['bb_dev']}, rsi_period={best_result['rsi_period']}")
    print(f"🔹 Sharpe Ratio:  {format_float(best_result['sharpe'])}")
    print(f"🔹 Max Drawdown:  {format_float(best_result['maxdd'])}%")
    print(f"🔹 Annual Return: {format_float(best_result['annual'] * 100 if best_result['annual'] else None, 4)}%")
    print(f"🔹 Average Return:{format_float(best_result['average'] * 100 if best_result['average'] else None, 4)}%")

    # 最佳夏普
    print("\n📊 最佳夏普参数组合:")
    print(f"周期: {best_sharpe_result['interval']}, bb_period={best_sharpe_result['bb_period']}, bb_dev={best_sharpe_result['bb_dev']}, rsi_period={best_sharpe_result['rsi_period']}")
    print(f"🔹 Sharpe Ratio:  {format_float(best_sharpe_result['sharpe'])}")
    print(f"🔹 Max Drawdown:  {format_float(best_sharpe_result['maxdd'])}%")
    print(f"🔹 Annual Return: {format_float(best_sharpe_result['annual'] * 100 if best_sharpe_result['annual'] else None, 4)}%")
    print(f"🔹 Average Return:{format_float(best_sharpe_result['average'] * 100 if best_sharpe_result['average'] else None, 4)}%")

    # 使用最佳夏普参数组合绘图
    print("\n📈 使用最佳夏普参数重新回测并绘图...")
    run_backtest_and_plot(
        interval=best_sharpe_result['interval'],
        bb_period=best_sharpe_result['bb_period'],
        bb_dev=best_sharpe_result['bb_dev'],
        rsi_period=best_sharpe_result['rsi_period'],
        plot=True
    )

if __name__ == '__main__':
    main()
