# 因子模块与 Nova 调用 API 说明

本文档说明当前量化项目里已经落地的因子模块能力，以及后续给 Nova 调用时可以直接使用的 API。

## 当前能力

当前版本已经支持两条因子策略路径：

1. **模板因子策略**
   - 通过 `factor_configs` 配置估值/动量类因子
   - 平台负责股票池、排序、TopN、调仓和回测

2. **Python 脚本因子策略**
   - 支持在前端**上传 `.py` 文件**
   - 支持在前端**直接新增 / 编辑 Python 脚本**
   - 支持两种脚本协议：
     - `score_stocks(histories, context)`：脚本返回每只股票分数，平台负责选股/调仓
     - `select_portfolio(histories, context)`：脚本直接返回目标组合，平台负责执行回测

## 认证 / 调用方式

当前版本已经切换为**本地无登录模式**，主要用于在 Windows 本机直接运行量化系统，并让后续 Nova 通过 HTTP 直接调用本机 API。

因此当前 `/api/*` 接口默认**不再要求登录 token**，请求时只需要：

```http
Content-Type: application/json
```

如果后续重新启用鉴权，需要再补一层网关或 token 方案；本文档以下示例全部按当前的无鉴权本地模式给出。

## 策略管理 API

### 1. 获取策略列表

`GET /api/strategy/list`

返回内置技术策略、内置因子模板，以及用户保存的自定义脚本策略。

关键字段：

- `id`
- `name`
- `type`：`tech` / `pattern` / `ml` / `factor` / `custom`
- `params`
- `code`：仅用户自定义策略会返回，保存的 Python 脚本内容
- `builtin`

### 2. 新建策略

`POST /api/strategy/create`

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

### 3. 更新策略

`PUT /api/strategy/{strategy_id}`

可更新：

- `name`
- `description`
- `params`
- `code`
- `enabled`

### 4. 获取单个策略

`GET /api/strategy/{strategy_id}`

用于读取完整配置和脚本内容。

## 因子回测 API

### 1. 运行因子回测

`POST /api/backtest/factor/run`

这是后续 Nova 最核心的调用入口。

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

#### 方式 B：直接传 inline Python 脚本

```json
{
  "script": "def score_stocks(histories, context):\n    return {code: rows[-1]['close'] for code, rows in histories.items()}",
  "top_n": 5,
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "capital": 100000,
  "rebalance": "monthly",
  "pool_codes": ["sh.600000", "sz.000001"]
}
```

#### 方式 C：调用已保存的脚本策略

```json
{
  "strategy_id": "custom_factor_script",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "capital": 100000,
  "pool_codes": ["sh.600000", "sz.000001"]
}
```

如果 `strategy_id` 对应的策略保存了 `code` 和默认 `params`，后端会自动补齐脚本、`top_n` 和 `rebalance` 等配置。

### 返回格式

```json
{
  "data": {
    "run_id": "factor_xxxxxxxxxx",
    "pool_size": 2,
    "rebalance": "monthly",
    "metrics": {
      "final_equity": 102738.8,
      "total_return": 2.74,
      "rebalance_count": 24
    },
    "equity_curve": [
      {"date": "2023-01-31", "equity": 100000.0}
    ],
    "rebalances": [
      {
        "date": "2023-01-31",
        "selected": [
          {"code": "sh.600000", "score": 1.23}
        ],
        "positions": [
          {"code": "sh.600000", "amount": 10000}
        ],
        "cash": 1234.56
      }
    ]
  }
}
```

### 2. 查询因子回测结果

`GET /api/backtest/factor/{run_id}`

返回结构：

```json
{
  "data": {
    "run_id": "factor_xxxxxxxxxx",
    "status": "success",
    "metrics": {...},
    "equity_curve": [...],
    "rebalances": [...]
  }
}
```

## Python 脚本协议

后端目前支持两种脚本入口，二选一即可。

### 协议 A：`score_stocks(histories, context)`

适合“脚本只负责打分，平台负责选股与调仓”。

```python
def score_stocks(histories, context):
    scores = {}
    for code, rows in histories.items():
        if not rows:
            continue
        scores[code] = rows[-1]["close"]
    return scores
```

要求：

- 返回 `dict[code, score]`
- 分数越大越优
- 平台会按分数倒序，截取 `top_n`

### 协议 B：`select_portfolio(histories, context)`

适合“脚本直接决定组合”。

```python
def select_portfolio(histories, context):
    return [
        {"code": "sz.000001", "weight": 1.0}
    ]
```

也支持：

```python
def select_portfolio(histories, context):
    return {
        "sz.000001": 0.7,
        "sh.600000": 0.3
    }
```

要求：

- 可以返回 `list[dict]`、`dict[code, weight]` 或 `list[str]`
- 如果没传权重，平台按等权处理
- 平台负责交易成本、权益曲线和调仓结果输出

## 脚本运行上下文

`context` 当前包含：

- `date`
- `start_date`
- `end_date`
- `rebalance`
- `top_n`

`histories` 结构：

```python
{
  "sh.600000": [
    {
      "date": "2024-01-31",
      "close": 9.98,
      "amount": 380000000.0,
      "turn": 0.11,
      "peTTM": 5.2,
      "pbMRQ": 0.47,
      "psTTM": 1.03,
      "pcfNcfTTM": 2.11
    }
  ]
}
```

## 当前内置可直接复用的字段

目前数据库已具备这些字段，可直接用于 Nova 侧脚本：

- `close`
- `amount`
- `turn`
- `peTTM`
- `pbMRQ`
- `psTTM`
- `pcfNcfTTM`

## Nova 调用建议

Nova 后续建议直接调用运行在 **Windows 本机** 的量化服务，而不是走当前性能较弱的服务器部署。

推荐流程：

1. 让本地服务启动在可访问地址（例如 `http://<windows-host>:8000`）
2. Nova 直接调用 `POST /api/backtest/factor/run`
3. 在三种模式里选一种：
   - 直接传 `factor_configs`
   - 直接传 `script`
   - 传 `strategy_id` 调用已保存脚本
4. 拿到 `run_id`
5. 轮询 `GET /api/backtest/factor/{run_id}`
6. 读取 `metrics` / `equity_curve` / `rebalances`

推荐 Nova 优先用 **方式 B / C**，因为脚本能力更灵活，适合自动生成和反复试验。

## 相关代码位置

- `backend/app/api/backtest.py`
- `backend/app/api/strategy.py`
- `backend/app/core/factor_runner.py`
- `backend/app/core/factor_backtest.py`
- `backend/app/factors/base.py`
- `backend/app/factors/builtin.py`
- `frontend/modules/pages/backtest.js`
- `frontend/modules/api/client.js`
