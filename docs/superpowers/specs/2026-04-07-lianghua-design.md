# 量化交易系统（lianghua）设计文档

## 概述

A股自动量化分析交易系统，支持策略回测和实盘自动交易。

**目标用户：** 个人投资者
**资金规模：** 初期10万内，按100万规模设计
**核心功能：** 策略回测 + 实盘自动交易 + 风控 + Web可视化

## 技术栈

| 层面 | 技术选型 | 理由 |
|------|----------|------|
| 后端 | FastAPI + APScheduler | 异步高性能，原生WebSocket支持，定时任务调度 |
| 前端 | 原生 ES Module | 无构建工具，改完刷新即见效，模块化清晰 |
| 图表 | Lightweight Charts v5 | TradingView开源金融图表库，K线渲染性能极佳 |
| 通信 | REST + WebSocket | REST处理历史数据和回测触发，WebSocket推送实时行情和进度 |
| 数据库 | SQLite | 轻量，够用，单机部署 |
| 数据源 | baostock | 免费，日线数据 |
| 计算 | talib + Numba | 指标计算全部在后端 |
| 券商 | 同花顺 eTrade | 实盘交易对接 |

## 架构

FastAPI 后端 + APScheduler 定时任务 + 原生 ES Module 前端。回测在子进程中运行，不阻塞Web服务。前端由 FastAPI 静态文件服务托管。

```
用户浏览器
    │
    ├── REST API ──→ FastAPI ──→ 业务逻辑
    │                   │
    └── WebSocket ──→ FastAPI ──→ 实时推送
                        │
                   APScheduler ──→ 定时策略执行
                        │
                   子进程 ──→ 回测计算
```

## 目录结构

```
lianghua/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口 + WebSocket + 静态文件托管
│   │   ├── api/                   # REST API 路由
│   │   │   ├── backtest.py        # 回测接口：启动回测、查询进度、获取结果
│   │   │   ├── strategy.py        # 策略管理：列表、参数配置、启停
│   │   │   ├── trading.py         # 交易接口：持仓、下单、撤单、交易记录
│   │   │   ├── market.py          # 行情接口：K线数据、股票列表、搜索
│   │   │   └── monitor.py         # 监控接口：系统状态、调度任务、日志
│   │   ├── ws/                    # WebSocket 处理
│   │   │   ├── market.py          # 实时行情推送
│   │   │   └── progress.py        # 回测进度推送
│   │   ├── core/                  # 核心业务
│   │   │   ├── engine.py          # 回测/交易引擎（统一引擎，回测和实盘共用策略代码）
│   │   │   ├── scheduler.py       # APScheduler 任务调度
│   │   │   ├── indicators.py      # 技术指标计算 (talib + Numba)
│   │   │   └── config.py          # 全局配置
│   │   ├── strategies/            # 策略实现
│   │   │   ├── base.py            # 策略基类
│   │   │   ├── tech/              # 技术指标策略 (MA交叉, MACD, RSI, 布林带)
│   │   │   ├── ml/                # AI/ML策略 (sklearn, lightgbm)
│   │   │   └── pattern/           # 形态策略 (强势平台整理后启动)
│   │   ├── data/                  # 数据层
│   │   │   ├── provider.py        # DataProvider 抽象接口
│   │   │   ├── baostock.py        # baostock 实现
│   │   │   └── storage.py         # SQLite 存储/缓存
│   │   ├── broker/                # 券商接口
│   │   │   ├── base.py            # Broker 抽象基类
│   │   │   ├── ths.py             # 同花顺 eTrade 实现
│   │   │   └── simulator.py       # 模拟券商（回测用，含滑点和手续费模拟）
│   │   ├── risk/                  # 风控模块
│   │   │   ├── manager.py         # 风控管理器（三层检查流水线）
│   │   │   ├── position.py        # 仓位管理
│   │   │   └── rules.py           # 风控规则（止损、黑名单）
│   │   └── models/                # 数据模型
│   │       ├── db.py              # SQLite 数据库初始化和连接
│   │       └── schemas.py         # Pydantic 数据模型
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # 主入口
│   ├── modules/                   # ES Module 模块
│   │   ├── app.js                 # 应用入口 + hash路由
│   │   ├── chart/                 # Lightweight Charts v5 封装
│   │   │   ├── kline.js           # K线图组件
│   │   │   ├── indicators.js      # 指标图层叠加
│   │   │   └── drawing.js         # 绘图工具
│   │   ├── pages/                 # 页面模块
│   │   │   ├── platform.js        # 主平台：K线 + 行情 + 持仓 + 交易记录
│   │   │   ├── backtest.js        # 策略验证：选策略 → 回测 → 结果展示
│   │   │   ├── data.js            # 数据管理：下载进度、更新状态、质量检查
│   │   │   └── ops.js             # 运维：系统状态、调度任务、日志、配置
│   │   ├── ws/                    # WebSocket 客户端
│   │   │   └── client.js          # WebSocket 连接管理
│   │   └── api/                   # REST API 调用封装
│   │       └── client.js          # API 客户端
│   └── static/                    # 静态资源
│       └── style.css              # 样式（Pico CSS 基础 + 自定义）
└── data/
    ├── market/                    # 行情数据缓存（SQLite）
    └── db/                        # 业务数据库
```

## 模块详细设计

### 1. 数据层

**数据源接口：**
```python
class DataProvider(ABC):
    def get_daily(self, code, start_date, end_date) -> pd.DataFrame: ...
    def get_stock_list(self) -> pd.DataFrame: ...
    def get_trade_calendar(self, start_date, end_date) -> list[str]: ...
```

**数据流：**
1. 首次使用：批量下载历史日线数据（2015年至今），存入 SQLite
2. 每日增量：APScheduler 在 15:30 触发，更新当日数据
3. API 查询：从本地 SQLite 读取，缺失范围自动从远程补充

**SQLite 表结构：**
- `stock_daily`: code, date, open, high, low, close, volume, amount, turn, peTTM, pbMRQ, psTTM, pcfNcfTTM
- `stock_info`: code, name, industry, listed_date, delisted_date, status
- `trade_calendar`: date, is_trading_day

### 2. 策略引擎

**策略基类：**
```python
class Strategy(ABC):
    name: str
    params: dict  # 可配置参数

    def init(self, config: dict): ...
    def on_bar(self, bar: dict, context: Context) -> list[Signal]: ...
```

**Context 对象：**
```python
class Context:
    positions: dict       # 当前持仓 {code: Position}
    balance: float        # 可用资金
    total_value: float    # 总资产
    history: pd.DataFrame # 历史数据窗口
    date: str             # 当前日期
```

**Signal 对象：**
```python
class Signal:
    code: str             # 股票代码
    action: str           # "buy" | "sell"
    price: float          # 目标价格
    amount: int           # 目标数量（手）
    reason: str           # 信号原因
```

**统一引擎：** 回测和实盘共用同一个 Strategy 代码
- 回测模式：读取历史数据，逐bar回放，SimBroker 执行
- 实盘模式：每日收盘后触发，THSBroker 执行

**策略类型：**
- `tech/ma_cross.py` — 均线交叉策略
- `tech/macd.py` — MACD 金叉死叉
- `tech/rsi.py` — RSI 超买超卖
- `tech/bollinger.py` — 布林带突破
- `ml/lightgbm_pred.py` — LightGBM 涨跌预测
- `pattern/platform_breakout.py` — 强势平台整理后启动

**回测输出指标：**
- 累计收益曲线 + 基准（沪深300）对比
- 最大回撤、夏普比率、年化收益率
- 胜率、盈亏比
- 逐笔交易记录
- 月度/年度收益统计表

### 3. 券商接口

**抽象层：**
```python
class Broker(ABC):
    def buy(self, code, price, amount) -> Order: ...
    def sell(self, code, price, amount) -> Order: ...
    def get_positions(self) -> list[Position]: ...
    def get_balance(self) -> Balance: ...
    def get_orders(self, date=None) -> list[Order]: ...
    def cancel_order(self, order_id) -> bool: ...
```

**SimBroker（模拟券商，回测用）：**
- 模拟成交：下一bar的开盘价成交
- 滑点模拟：0.1%
- 手续费：佣金万2.5 + 印花税千1（卖出） + 过户费十万分之一

**THSBroker（同花顺 eTrade，实盘用）：**
- 对接同花顺 eTrade API
- 支持限价单/市价单
- 委托状态查询和撤单

### 4. 风控系统

**三层风控流水线：** 策略信号 → 仓位检查 → 止损检查 → 黑名单检查 → 通过才下单

**第一层 — 仓位管理：**
- 单只股票最大仓位：总资金的 20%（可配置）
- 每日最大交易金额：总资金的 50%
- 最大持仓数量：5-10只（可配置）

**第二层 — 止损规则：**
- 个股止损：买入后下跌 -5% 触发（可配置）
- 总账户止损：当日亏损达总资金 -3% 停止交易
- 追踪止损：从最高点回撤 -8% 卖出

**第三层 — 黑名单/过滤规则：**
- 禁止交易 ST/*ST 股票
- 禁止交易上市不满 60 天的新股
- 禁止交易停牌/一字涨跌停股票
- 用户自定义黑名单

### 5. 任务调度

**APScheduler 定时任务：**
- 每日 15:30 — 增量更新行情数据
- 每日 15:00 — 运行实盘策略，生成交易信号
- 每日 09:25 — 执行盘前信号的委托下单
- 每周末 — 数据完整性检查

### 6. Web 界面

**页面设计：**

**主平台页（platform）：**
- Lightweight Charts v5 K线图，支持滚动缩放、十字光标
- 技术指标叠加（MA、MACD、RSI、布林带）
- 当前持仓列表 + 盈亏状态
- 当日交易记录
- 股票搜索和切换

**策略验证页（backtest）：**
- 策略选择 + 参数配置表单
- 回测时间范围设定
- 回测进度条（WebSocket 推送）
- 结果展示：收益曲线图、关键指标卡片、交易记录表

**数据管理页（data）：**
- 数据下载状态和进度
- 数据更新日志
- 数据质量检查报告

**运维页（ops）：**
- 系统状态监控
- APScheduler 任务列表和状态
- 运行日志查看
- 全局配置管理

**前端路由：** hash-based 路由
- `#/platform` — 主平台
- `#/backtest` — 策略验证
- `#/data` — 数据管理
- `#/ops` — 运维系统

## 部署

**本地开发：**
```bash
# 后端
cd backend && pip install -r requirements.txt
python -m app.main

# 前端由 FastAPI 静态文件服务托管，无需额外启动
```

**服务器部署（43.134.73.213）：**
- 用 systemd 或 supervisor 管理 FastAPI 进程
- 配置文件：`~/.lianghua/config.json`
- 数据目录：`~/lianghua-data/`

## 开发顺序（建议）

1. **Phase 1：数据基础** — 数据下载、存储、API
2. **Phase 2：策略引擎** — 回测引擎、策略基类、1-2个示例策略
3. **Phase 3：Web基础** — K线图展示、回测结果可视化
4. **Phase 4：风控系统** — 仓位管理、止损、黑名单
5. **Phase 5：实盘对接** — 同花顺 eTrade 集成、实盘调度
6. **Phase 6：高级策略** — AI/ML策略、形态识别策略
