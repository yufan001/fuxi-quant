# 因子模块与 Nova 调用 API 说明

本文档说明当前量化项目里已经落地的因子模块能力，以及后续给 Nova 调用时可以直接使用的 API。当前推荐模式是：**异步 HTTP Job API 优先，MCP 作为 Nova 侧包装层。**

## 当前能力

当前版本已经支持：

- 同步因子回测 API
- 异步 Job API（适合 Nova 自动调用）
- Job 取消能力
- 结果 artifact 落盘与 artifact API
- Python 脚本因子策略
- webhook + 轮询双模式获取结果
- 本地无登录运行模式

当前版本已经支持两条因子策略路径：

1. **模板因子策略**
   - 通过 `factor_configs` 配置估值/动量类因子
   - 平台负责股票池、排序、TopN、调仓和回测

2. **Python 脚本因子策略**
   - 支持在前端**上传 `.py` 文件**
   - 支持在前端**直接新增 / 编辑 Python 脚本**
   - 支持三种脚本协议：
     - `score_stocks(histories, context)`：脚本返回每只股票分数，平台负责选股/调仓
     - `score_frame(frame, context)`：脚本直接接收表格化历史数据，适合向量化打分
     - `select_portfolio(histories, context)`：脚本直接返回目标组合，平台负责执行回测

## 认证 / 调用方式

当前版本已经切换为**本地无登录模式**，主要用于在 Windows 本机直接运行量化系统，并让后续 Nova 通过 HTTP 直接调用本机 API。

因此当前 `/api/*` 接口默认**不再要求登录 token**，请求时只需要：

```http
Content-Type: application/json
```

如果后续重新启用鉴权，需要再补一层网关或 token 方案；本文档以下示例全部按当前的无鉴权本地模式给出。

## 数据来源

当前股票历史数据来自 **baostock**，核心代码：

- `backend/app/data/baostock_provider.py`
- `backend/app/data/downloader.py`

服务器上已经确认存在一份可回流的完整历史数据库：

- 路径：`/root/lianghua/data/market/market.db`
- 大小：约 `2.2G`
- 日期范围：`2015-01-05` ~ `2026-04-10`
- 股票数：`7182`

这份库后续可以先拉回本地，再调用异步导入任务导入到当前 Fuxi 实例。

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

## 同步因子回测 API

### 1. 运行因子回测

`POST /api/backtest/factor/run`

这是保留给本地调试和前端直接调用的同步入口。Nova 自动化建议优先走下方异步 Job API。

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

脚本请求还支持可选字段 `script_timeout_seconds`，必须是正数；未传时默认使用 `10` 秒。

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

## 异步 Job API（推荐给 Nova）

### 1. 提交因子回测任务

`POST /api/jobs/backtest/factor`

示例：

```json
{
  "strategy_id": "custom_factor_script",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "pool_codes": ["sh.600000", "sz.000001"],
  "script_timeout_seconds": 15,
  "callback_url": "http://127.0.0.1:18790/api/fuxi/webhook",
  "callback_secret": "your-shared-secret"
}
```

返回：

```json
{
  "data": {
    "job_id": "job_xxxxxxxxxxxx",
    "status": "queued"
  }
}
```

### 2. 查询任务状态

`GET /api/jobs/{job_id}`

返回示例：

```json
{
  "data": {
    "id": "job_xxxxxxxxxxxx",
    "job_type": "factor_backtest",
    "status": "running",
    "progress": {
      "percent": 10,
      "message": "factor_backtest_loading_data"
    },
    "error": null,
    "created_at": "2026-04-13T01:00:00Z",
    "started_at": "2026-04-13T01:00:01Z",
    "finished_at": null
  }
}
```

### 3. 获取完整结果

`GET /api/jobs/{job_id}/result`

这里返回完整 `metrics / equity_curve / rebalances`，同时会附带：

- `_summary`
- `_artifacts`

适合 Nova 在任务完成后拉取最终结果。

### 4. 获取任务日志

`GET /api/jobs/{job_id}/logs`

### 5. 获取 artifact 清单

`GET /api/jobs/{job_id}/artifacts`

### 6. 获取单个 artifact 内容

`GET /api/jobs/{job_id}/artifacts/{artifact_name}`

如果是 `application/json` 会直接返回解析后的 JSON；文本文件返回字符串内容；二进制文件返回 base64 文本。

### 7. 取消任务

`POST /api/jobs/{job_id}/cancel`

语义：

- `queued`：直接转为 `cancelled`
- `running`：标记 `cancel_requested=1`，handler 在阶段边界协作式终止

### 8. 提交数据任务

#### 增量更新 / 数据清洗入口

`POST /api/jobs/data/update`

```json
{
  "mode": "incremental"
}
```

#### 导入数据库文件

`POST /api/jobs/data/import-db`

```json
{
  "source_path": "D:/AAA/fuxi-seed/market.db",
  "replace_existing": true
}
```

### 6. webhook 回调格式

如果提交任务时带了 `callback_url`，任务完成后 Fuxi 会 POST 到该地址。

回调头：

- `X-Fuxi-Timestamp`
- `X-Fuxi-Signature`

签名算法：

- `sha256(secret, "{timestamp}.{body}")`

回调体：

```json
{
  "job_id": "job_xxxxxxxxxxxx",
  "job_type": "factor_backtest",
  "status": "success",
  "summary": {
    "final_equity": 102738.8,
    "total_return": 2.74,
    "rebalance_count": 24,
    "pool_size": 2
  },
  "artifacts": [
    {"name": "summary.json", "mime_type": "application/json", "size_bytes": 128}
  ],
  "result": {
    "metrics": {...},
    "equity_curve": [...],
    "rebalances": [...]
  },
  "error": null
}
```

因此 Nova 侧可以：

- 被动接 webhook
- 主动轮询 `/api/jobs/{job_id}` 和 `/api/jobs/{job_id}/result`
- 拉取 `/api/jobs/{job_id}/artifacts` 拿到大结果文件清单
- 必要时调用 `/api/jobs/{job_id}/cancel`

两种一起开，做双保险。

## MCP 包装层

Fuxi 已提供：

- `backend/app/mcp_server.py`

可直接运行：

```bash
python -m app.mcp_server
```

当前 MCP tools 包括：

- `submit_factor_backtest`
- `get_job_status`
- `get_job_result`
- `get_job_artifacts`
- `get_job_logs`
- `cancel_job`
- `submit_data_update`
- `submit_data_import`

这些工具本质上是对上面异步 HTTP API 的包装，因此 HTTP API 永远是主接口，MCP 只是 Nova 侧更自然的接入方式。

### MCP 统一返回结构

所有 MCP tools 现在都返回统一 envelope：

```json
{
  "ok": true,
  "data": {...},
  "error": null
}
```

失败时：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "job_not_found",
    "message": "任务不存在"
  }
}
```

Nova 侧建议：

1. 优先读取 `structuredContent`
2. 仅在客户端没有提供 `structuredContent` 时，再回退到第一个 `TextContent.text`
3. 判断成功只看 `ok`
4. 分支处理优先看 `error.code`

### MCP tools 返回字段约定

#### 1. `submit_factor_backtest`

输入：

- `base_url`
- `start_date`
- `end_date`
- `strategy_id` / `script`
- `factor_configs`
- `top_n`
- `capital`
- `rebalance`
- `pool_codes`
- `callback_url`
- `callback_secret`

返回：

```json
{
  "ok": true,
  "data": {
    "job": {
      "id": "job_xxxxxxxxxxxx",
      "status": "queued"
    }
  },
  "error": null
}
```

#### 2. `get_job_status`

返回：

```json
{
  "ok": true,
  "data": {
    "job": {
      "id": "job_xxxxxxxxxxxx",
      "job_type": "factor_backtest",
      "status": "running",
      "progress": {
        "percent": 10,
        "message": "factor_backtest_loading_data"
      },
      "summary": {},
      "artifacts": [],
      "cancel_requested": false,
      "error": null,
      "created_at": "2026-04-13T01:00:00Z",
      "started_at": "2026-04-13T01:00:01Z",
      "finished_at": null
    }
  },
  "error": null
}
```

#### 3. `get_job_result`

返回字段固定在 `data.result`：

```json
{
  "ok": true,
  "data": {
    "result": {
      "metrics": {...},
      "equity_curve": [...],
      "rebalances": [...],
      "_summary": {...},
      "_artifacts": [...]
    }
  },
  "error": null
}
```

#### 4. `get_job_artifacts`

返回字段固定在 `data.artifacts`：

```json
{
  "ok": true,
  "data": {
    "artifacts": [
      {
        "name": "summary.json",
        "mime_type": "application/json",
        "size_bytes": 128,
        "path": "..."
      }
    ]
  },
  "error": null
}
```

#### 5. `get_job_logs`

返回字段固定在 `data.logs`：

```json
{
  "ok": true,
  "data": {
    "logs": [
      "job_started",
      "factor_backtest_finished"
    ]
  },
  "error": null
}
```

#### 6. `cancel_job`

返回字段固定在 `data.job`，表示取消请求后的最新 job 状态：

```json
{
  "ok": true,
  "data": {
    "job": {
      "id": "job_xxxxxxxxxxxx",
      "status": "cancel_requested"
    }
  },
  "error": null
}
```

#### 7. `submit_data_update` / `submit_data_import`

两者与 `submit_factor_backtest` 一致，提交后都返回：

```json
{
  "ok": true,
  "data": {
    "job": {
      "id": "job_xxxxxxxxxxxx",
      "status": "queued"
    }
  },
  "error": null
}
```

### MCP 结构化错误码

当前 MCP 层统一收敛这些常见错误码：

- `job_not_found`
- `artifact_not_found`
- `job_cancel_failed`
- `http_request_failed`
- `upstream_invalid_response`

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

1. 本地启动 Fuxi API
2. Nova 优先调用异步 Job API：
   - `POST /api/jobs/backtest/factor`
   - `GET /api/jobs/{job_id}`
   - `GET /api/jobs/{job_id}/result`
3. 如需更 agent-native 的方式，再通过 `python -m app.mcp_server` 暴露 MCP tools
4. 对 Nova 来说，最灵活的是：
   - 直接传 `script`
   - 或传 `strategy_id` 调用已保存脚本策略

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
