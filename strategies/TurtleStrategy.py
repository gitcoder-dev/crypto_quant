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
def get_binance_btc_data(symbol='BTCUSDT', interval='1h', lookback_days=900):
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

# 海龟策略
class TurtleATRStrategy(bt.Strategy):
    params = (
        ('entry_period', 20),
        ('exit_period', 10),
        ('atr_period', 14),
        ('risk_per_trade', 0.01),
        ('max_units', 4),  # 最多加仓次数
    )

    def __init__(self):
        self.entry_high = bt.ind.Highest(self.data.high, period=self.p.entry_period)
        self.exit_low = bt.ind.Lowest(self.data.low, period=self.p.exit_period)
        self.atr = bt.ind.ATR(self.data, period=self.p.atr_period)
        self.unit_size = 0
        self.last_entry_price = None
        self.units = 0
        self.order = None
        self.trade_count = 0

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None
    
    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_count += 1

    def next(self):
        if self.order:
            return

        cash = self.broker.get_cash()

        if not self.position:
            if self.data.close[0] > self.entry_high[-1]:
                risk_amount = cash * self.p.risk_per_trade
                self.unit_size = risk_amount / self.atr[0]
                self.last_entry_price = self.data.close[0]
                self.units = 1
                self.order = self.buy(size=self.unit_size)
        else:
            # 加仓逻辑：每次上涨0.5ATR时加一次仓
            if self.units < self.p.max_units:
                if self.data.close[0] >= self.last_entry_price + 0.5 * self.atr[0]:
                    self.order = self.buy(size=self.unit_size)
                    self.last_entry_price = self.data.close[0]
                    self.units += 1

            # 平仓逻辑：跌破 exit 通道 或者 价格低于最后入场价 - 2ATR（止损）
            stop_price = self.last_entry_price - 2 * self.atr[0]
            if self.data.close[0] < self.exit_low[-1] or self.data.close[0] < stop_price:
                self.order = self.sell(size=self.position.size)
                self.units = 0

# 设置Backtrader
def run_backtest_and_plot(interval, entry_period, exit_period, atr_period, plot=False):
    df = get_binance_btc_data(interval=interval)
    data = PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.0008)
    cerebro.adddata(data)

    cerebro.addstrategy(
        TurtleATRStrategy,
        entry_period=entry_period,
        exit_period=exit_period,
        atr_period=atr_period
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
    total_trades = strat.trade_count

    # 输出分析结果
    print(f"[{interval}] entry={entry_period}, exit={exit_period}, atr={atr_period} | "
          f"Sharpe: {format_float(sharpe)}, "
          f"Return: {format_float(rtot * 100 if rtot is not None else None)}%, "
          f"MaxDD: {format_float(maxdd)}%, "
          f"Annual: {format_float(annual * 100 if annual is not None else None)}%, "
          f"Avg: {format_float(average * 100 if average is not None else None)}%"
          f"Trades Count:{total_trades}")

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
        'entry': entry_period,
        'exit': exit_period,
        'atr': atr_period,
        'sharpe': sharpe,
        'return': rtot,
        'maxdd': maxdd,
        'annual': annual,
        'average': average,
        'trades':total_trades,
    }


def format_float(value, digits=2):
    return f"{value:.{digits}f}" if value is not None else "N/A"

def main():
    best_result = None
    best_annual = -float('inf')
    best_sharpe_result = None
    best_sharpe = -float('inf')
    all_results = []

    intervals = ['1h']
    entry_range = range(10, 11, 5)
    exit_range = range(20, 41, 5)
    atr_range = range(10, 20, 5)

    print("🔍 正在进行参数优化...\n")

    for interval in intervals:
        for entry_p in entry_range:
            for exit_p in exit_range:
                for atr_p in atr_range:
                    result = run_backtest_and_plot(interval, entry_p, exit_p, atr_p, plot=False)
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
    print(f"周期: {best_result['interval']}, entry={best_result['entry']}, exit={best_result['exit']}, atr={best_result['atr']}")
    print(f"🔹 Sharpe Ratio:  {format_float(best_result['sharpe'])}")
    print(f"🔹 Max Drawdown:  {format_float(best_result['maxdd'])}%")
    print(f"🔹 Annual Return: {format_float(best_result['annual'] * 100 if best_result['annual'] else None, 4)}%")
    print(f"🔹 Average Return:{format_float(best_result['average'] * 100 if best_result['average'] else None, 4)}%")
    print(f"🔹count: {best_result['trades']}")

    # 最佳夏普
    print("\n📊 最佳夏普参数组合:")
    print(f"周期: {best_sharpe_result['interval']}, entry={best_sharpe_result['entry']}, exit={best_sharpe_result['exit']}, atr={best_sharpe_result['atr']}")
    print(f"🔹 Sharpe Ratio:  {format_float(best_sharpe_result['sharpe'])}")
    print(f"🔹 Max Drawdown:  {format_float(best_sharpe_result['maxdd'])}%")
    print(f"🔹 Annual Return: {format_float(best_sharpe_result['annual'] * 100 if best_sharpe_result['annual'] else None, 4)}%")
    print(f"🔹 Average Return:{format_float(best_sharpe_result['average'] * 100 if best_result['average'] else None, 4)}%")
    print(f"🔹count: {best_sharpe_result['trades']}")
    
    # 使用最佳年化参数组合绘图
    print("\n📈 使用最佳年化参数重新回测并绘图...")
    run_backtest_and_plot(
        interval=best_result['interval'],
        entry_period=best_result['entry'],
        exit_period=best_result['exit'],
        atr_period=best_result['atr'],
        plot=True
    )

    # 使用最佳夏普参数组合绘图
    print("\n📈 使用最佳夏普参数重新回测并绘图...")
    run_backtest_and_plot(
        interval=best_sharpe_result['interval'],
        entry_period=best_sharpe_result['entry'],
        exit_period=best_sharpe_result['exit'],
        atr_period=best_sharpe_result['atr'],
        plot=True
    )

if __name__ == '__main__':
    main()