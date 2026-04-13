# Fuxi Quant

本地优先的量化因子研究与回测系统。

当前项目重点不是“服务器常驻量化平台”，而是**在 Windows 本机直接运行**，把重的回测和数据清洗都放在本地做；后续 Nova 需要时，直接通过 HTTP 调用本机 API。

## 当前状态

已支持：

- 单股票技术策略回测
- 截面因子选股回测
- Python 脚本因子策略
  - 上传 `.py` 文件
  - 页面内直接新增 / 编辑脚本
  - 支持 `score_stocks()` 和 `select_portfolio()` 两种脚本协议
- 本地无登录模式
- Nova 可直接调用的因子回测 API

## 技术栈

### 后端

- **FastAPI**：API 服务与静态资源托管
- **SQLite**：行情与业务数据存储
- **APScheduler**：定时任务（当前项目里已有调度基础）
- **Python 因子脚本执行**：支持 inline script / saved strategy script

### 前端

- **原生 ES Module**
- **Lightweight Charts**：收益曲线与行情图表
- 当前 UI 已支持：
  - 策略库
  - 因子模板配置
  - 脚本上传与在线编辑
  - 因子回测结果面板

### 数据

当前可直接用于因子逻辑的字段主要来自 `stock_daily`：

- `close`
- `amount`
- `turn`
- `peTTM`
- `pbMRQ`
- `psTTM`
- `pcfNcfTTM`

## 目录结构

```text
lianghua/
├── backend/
│   └── app/
│       ├── api/
│       │   ├── backtest.py        # 技术策略 + 因子回测 API
│       │   ├── strategy.py        # 策略库 / 自定义脚本策略
│       │   └── market.py          # 行情与股票列表
│       ├── core/
│       │   ├── engine.py          # 单股票技术策略回测引擎
│       │   ├── factor_backtest.py # 截面因子组合回测引擎
│       │   └── factor_runner.py   # 因子任务入口（Nova 调用的核心路径）
│       ├── factors/
│       │   ├── base.py            # 因子打分基础能力
│       │   └── builtin.py         # 内置因子定义
│       └── data/
│           └── storage.py         # 多股票历史读取、交易日读取
├── frontend/
│   ├── index.html
│   └── modules/
│       ├── app.js
│       ├── api/client.js
│       └── pages/backtest.js
├── docs/
│   └── factor-module-api.md       # 面向 Nova 的因子 API 说明
└── README.md
```

## 本地运行

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

启动后直接访问：

- `http://127.0.0.1:8000/#/platform`
- `http://127.0.0.1:8000/#/backtest`

当前默认是**无登录模式**。

## 因子模块能力

### 1. 模板因子策略

通过 `factor_configs` 定义因子组合，例如：

- `pb`
- `pe`
- `ps`
- `momentum_20`
- `momentum_60`
- `momentum_120`

平台负责：

- 股票池读取
- 截面排序
- TopN 选股
- 调仓
- 交易成本计算
- 权益曲线与调仓结果输出

### 2. Python 脚本因子策略

支持两种脚本协议：

#### A. 分数脚本

```python
def score_stocks(histories, context):
    return {code: rows[-1]["close"] for code, rows in histories.items()}
```

#### B. 组合脚本

```python
def select_portfolio(histories, context):
    return [
        {"code": "sz.000001", "weight": 1.0}
    ]
```

## 核心 API

### 获取策略列表

```http
GET /api/strategy/list
```

### 新建脚本策略

```http
POST /api/strategy/create
Content-Type: application/json
```

```json
{
  "name": "脚本因子测试",
  "type": "factor",
  "description": "按脚本分数选股",
  "params": {
    "top_n": 5,
    "rebalance": "monthly"
  },
  "code": "def score_stocks(histories, context):\n    return {code: rows[-1]['close'] for code, rows in histories.items()}"
}
```

### 运行因子回测

```http
POST /api/backtest/factor/run
Content-Type: application/json
```

支持三种调用方式：

#### 方式 A：模板因子配置

```json
{
  "factor_configs": [
    {"key": "pb", "weight": 0.5},
    {"key": "momentum_20", "weight": 0.5}
  ],
  "top_n": 10,
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "capital": 100000,
  "rebalance": "monthly",
  "pool_codes": ["sh.600000", "sz.000001"]
}
```

#### 方式 B：直接传 inline 脚本

```json
{
  "script": "def select_portfolio(histories, context):\n    return [{\"code\": \"sz.000001\", \"weight\": 1.0}]",
  "top_n": 1,
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "capital": 100000,
  "rebalance": "monthly",
  "pool_codes": ["sh.600000", "sz.000001"]
}
```

#### 方式 C：调用已保存脚本策略

```json
{
  "strategy_id": "custom_xxxxxxxx",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "capital": 100000,
  "pool_codes": ["sh.600000", "sz.000001"]
}
```

### 查询因子回测结果

```http
GET /api/backtest/factor/{run_id}
```

## Nova 集成建议

当前推荐的接法：

1. 在 Windows 本机启动量化服务
2. 让 Nova 直接调用本机 HTTP API
3. 优先调用：
   - `POST /api/backtest/factor/run`
   - `GET /api/backtest/factor/{run_id}`
4. 对 Nova 来说，最灵活的是：
   - 直接传 `script`
   - 或传 `strategy_id` 调用已保存脚本策略

更详细的请求/响应结构，请看：

- [`docs/factor-module-api.md`](./docs/factor-module-api.md)

## 当前验证情况

当前已经验证：

- 后端测试通过
- 因子模板回测可用
- Python 脚本策略可用
- 前端支持上传 `.py` 文件并保存策略
- 前端支持在线编辑脚本并直接运行
- 本地无登录模式可直接进入 `#/backtest`
- 本地 API 已可被外部调用

## 仓库

- GitHub: `https://github.com/yufan001/fuxi-quant`
