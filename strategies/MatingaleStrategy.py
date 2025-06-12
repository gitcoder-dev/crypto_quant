from __future__ import (absolute_import, division, print_function, unicode_literals)

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
def get_binance_btc_data(symbol='BTCUSDT', interval='1h', lookback_days=300):
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

# 马丁格尔策略
class MartingaleStrategy(bt.Strategy):
    params = (
        ('initial_stake', 100),    # 初始投资金额
        ('multiplier', 2),         # 马丁格尔倍数
        ('take_profit_pct', 0.05), # 止盈百分比
        ('max_levels', 5),         # 最大加仓次数
        ('risk_pct', 0.02),        # 初始风险百分比
        ('ma_period', 20),         # 移动平均线周期，用于判断趋势
    )
    
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        # print(f'{dt.isoformat()} {txt}')
        
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        
        # 订单和持仓状态变量
        self.order = None
        self.entry_price = None
        self.level = 0
        self.current_stake = self.p.initial_stake
        
        # 移动平均线指标，用于确定趋势
        self.ma = bt.indicators.SMA(self.dataclose, period=self.p.ma_period)
        
        # 交易统计
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
            
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行: 价格: {order.executed.price:.2f}, 成本: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
                self.entry_price = order.executed.price
            else:
                self.log(f'卖出执行: 价格: {order.executed.price:.2f}, 成本: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
                profit_pct = (order.executed.price / self.entry_price - 1) * 100
                self.log(f'盈亏: {profit_pct:.2f}%')
                
                # 记录交易结果
                self.trade_count += 1
                if profit_pct > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                
                # 重置马丁格尔状态
                self.level = 0
                self.current_stake = self.p.initial_stake
                
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/拒绝')
            
        self.order = None
        
    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(f'交易利润: 毛利润 {trade.pnl:.2f}, 净利润 {trade.pnlcomm:.2f}')

    def next(self):
        # 确保没有未完成的订单
        if self.order:
            return
            
        # 计算账户风险管理
        portfolio_value = self.broker.getvalue()
        risk_amount = portfolio_value * self.p.risk_pct
        
        # 如果没有持仓，检查是否可以进入
        if not self.position:
            # 判断趋势，只在价格高于移动平均线时做多
            if self.dataclose[0] > self.ma[0]:
                size = self.current_stake / self.dataclose[0]
                self.log(f'买入 {size:.6f} BTC @ {self.dataclose[0]:.2f}')
                self.order = self.buy(size=size)
                self.level = 1
            
        # 如果有持仓，检查是否达到止盈条件或加仓条件
        elif self.entry_price:
            # 如果价格上涨达到止盈条件，卖出平仓
            if self.dataclose[0] >= self.entry_price * (1 + self.p.take_profit_pct):
                self.log(f'达到止盈条件，卖出 {self.position.size} BTC @ {self.dataclose[0]:.2f}')
                self.order = self.sell(size=self.position.size)
                
            # 如果价格下跌，根据马丁格尔策略加仓
            elif self.dataclose[0] < self.entry_price and self.level < self.p.max_levels:
                # 计算新的投资金额（按倍数增加）
                self.current_stake = self.p.initial_stake * (self.p.multiplier ** self.level)
                
                # 检查是否超过最大风险金额
                if self.current_stake <= risk_amount:
                    size = self.current_stake / self.dataclose[0]
                    self.log(f'加仓 {size:.6f} BTC @ {self.dataclose[0]:.2f} (Level {self.level+1})')
                    self.order = self.buy(size=size)
                    self.level += 1
                    # 更新平均持仓价格
                    self.entry_price = (self.entry_price * self.position.size + self.dataclose[0] * size) / (self.position.size + size)
                else:
                    self.log(f'加仓金额 {self.current_stake:.2f} 超过风险限制 {risk_amount:.2f}，跳过')
                    
            # 极端行情保护：如果价格下跌超过30%，止损出场
            elif self.dataclose[0] <= self.entry_price * 0.7:
                self.log(f'触发极端行情保护，止损卖出 {self.position.size} BTC @ {self.dataclose[0]:.2f}')
                self.order = self.sell(size=self.position.size)

# 运行回测并优化参数
def run_backtest_and_plot(interval, initial_stake, multiplier, take_profit_pct, max_levels, risk_pct, ma_period, plot=False):
    df = get_binance_btc_data(interval=interval)
    data = PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.0008)  # 币安现货手续费
    cerebro.adddata(data)

    cerebro.addstrategy(
        MartingaleStrategy,
        initial_stake=initial_stake,
        multiplier=multiplier,
        take_profit_pct=take_profit_pct,
        max_levels=max_levels,
        risk_pct=risk_pct,
        ma_period=ma_period
    )

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')

    # 运行回测
    results = cerebro.run()
    strat = results[0]

    # 获取分析结果
    sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', None)
    returns = strat.analyzers.returns.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trade_analysis = strat.analyzers.trade.get_analysis()

    rtot = returns.get('rtot', None)
    annual = returns.get('rnorm', None)
    average = returns.get('ravg', None)
    maxdd = drawdown.get('max', {}).get('drawdown', None)
    total_trades = strat.trade_count
    win_trades = strat.win_count
    loss_trades = strat.loss_count
    
    # 计算胜率
    win_rate = win_trades / total_trades if total_trades > 0 else 0

    # 输出分析结果
    print(f"[{interval}] stake={initial_stake}, mult={multiplier}, tp={take_profit_pct}, max_lvl={max_levels}, risk={risk_pct}, ma={ma_period} | "
          f"Sharpe: {format_float(sharpe)}, "
          f"Return: {format_float(rtot * 100 if rtot is not None else None)}%, "
          f"MaxDD: {format_float(maxdd)}%, "
          f"Annual: {format_float(annual * 100 if annual is not None else None)}%, "
          f"Avg: {format_float(average * 100 if average is not None else None)}%, "
          f"Trades: {total_trades}, "
          f"Win Rate: {format_float(win_rate * 100)}%")

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
        'initial_stake': initial_stake,
        'multiplier': multiplier,
        'take_profit_pct': take_profit_pct,
        'max_levels': max_levels,
        'risk_pct': risk_pct,
        'ma_period': ma_period,
        'sharpe': sharpe,
        'return': rtot,
        'maxdd': maxdd,
        'annual': annual,
        'average': average,
        'trades': total_trades,
        'win_rate': win_rate,
    }

def main():
    best_result = None
    best_annual = -float('inf')
    best_sharpe_result = None
    best_sharpe = -float('inf')
    all_results = []

    intervals = ['4h', '1d']
    initial_stakes = [100, 200, 300]
    multipliers = [1.5, 2, 2.5]
    take_profit_pcts = [0.03, 0.05, 0.07]
    max_levels_range = [3, 4, 5]
    risk_pcts = [0.02, 0.03, 0.05]
    ma_periods = [10, 20, 50]

    print("🔍 正在进行马丁格尔策略参数优化...\n")

    for interval in intervals:
        for initial_stake in initial_stakes:
            for multiplier in multipliers:
                for take_profit_pct in take_profit_pcts:
                    for max_levels in max_levels_range:
                        for risk_pct in risk_pcts:
                            for ma_period in ma_periods:
                                result = run_backtest_and_plot(
                                    interval, 
                                    initial_stake, 
                                    multiplier, 
                                    take_profit_pct, 
                                    max_levels, 
                                    risk_pct, 
                                    ma_period, 
                                    plot=False
                                )
                                
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
    print(f"周期: {best_result['interval']}, 初始投入: {best_result['initial_stake']}, 乘数: {best_result['multiplier']}, "
          f"止盈点: {best_result['take_profit_pct']}, 最大加仓次数: {best_result['max_levels']}, "
          f"风险比例: {best_result['risk_pct']}, MA周期: {best_result['ma_period']}")
    print(f"🔹 Sharpe Ratio:  {format_float(best_result['sharpe'])}")
    print(f"🔹 Max Drawdown:  {format_float(best_result['maxdd'])}%")
    print(f"🔹 Annual Return: {format_float(best_result['annual'] * 100 if best_result['annual'] else None, 4)}%")
    print(f"🔹 Average Return:{format_float(best_result['average'] * 100 if best_result['annual'] else None, 4)}%")

if __name__ == '__main__':
    main()