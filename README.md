# 🚀 Crypto_Quant

这是我在学习 **加密货币量化交易** 中的实战项目，基于 [Backtrader](https://www.backtrader.com/) 和 [Binance API](https://binance-docs.github.io/apidocs/spot/en/) 进行策略回测与优化分析。

欢迎大家一起交流策略、分享思路、共同进步 📈


## ✅ 已复现策略

- ✅ **双均线交叉策略**  
  使用短期和长期移动平均线判断买卖信号，并进行参数优化评估（回报率、夏普比率、最大回撤等）。
- ✅ **海龟策略**  
  利用唐安奇通道来跟踪趋势产生买卖信号，利用ATR（真实波幅均值）分批加仓或者减仓，并且动态进行止盈和止损。
- ✅ **布林带策略**  
  利用移动平均线和标准差来追踪价格波动。
- ✅ **资金费率套利策略**
  利用永续合约的资金费率进行套利。

策略原理请查看微信公众号文章。

## ⚡ 快速开始

1️⃣ 克隆项目或下载代码：

```bash
git clone https://github.com/Ashley0324/crypto_quant
cd crypto_quant
```

2️⃣ 安装依赖：

```bash
pip install -r requirements.txt
```

3️⃣ 运行策略主脚本：
```bash
python strategy.py
```
回测完成后会输出每组参数组合的绩效，并绘制最佳策略的图表结果（保存在 `performance_chart.png` 中）。

4️⃣ 添加api密钥

如果需要执行实盘，请将.env copy文件名改为.env并配置自己的api key和api secret。千万注意不能将该文件上传至git，以免账户被非法操作。

## 📁 项目结构说明

```bash
crypto_quant_exercise/
├── strategies              # 各个策略所在文件夹
├── requirements.txt        # 依赖清单
├── Dockerfile              # 可选，容器部署配置
├── data/                   # 本地缓存K线数据
├── output/                 # 策略图表与绩效输出
└── README.md               # 说明文档
```

## 📊 双均线交叉策略最佳结果

| 周期 | Short | Long | 回报率 | Sharpe | MaxDD |
|--------|--------|-------|------------|--------|--------|
| 1d     | 11     | 20    | 53.42%      | 1.15   | 9.25%  |

## 📊 海龟策略最佳结果

| 周期 | Entry | Exit | atr | Sharpe | MaxDD | Annual Return |
|--------|--------|-------|------------|--------|--------| --------|
| 1h     | 10    | 30    | 15      | 1.16   |   14.8%  | 42.82%  |

## 💬 交流讨论

欢迎通过以下方式联系我或参与讨论：

- 提 Issue 或 Pull Request
- 发邮件联系：ashleyjin0324@gmail.com
- telegram交流群：https://t.me/+PMkkHh0IfVU4ZTJl
- 微信公众号：泡芙写字的地方

## 🔐 免责声明
仅供技术学习交流，投资有风险，请自行评估。

---

> ✨ 项目持续更新中，别忘了 Star & Follow！
