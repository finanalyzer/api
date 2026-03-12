# 股票历史数据接口规格说明

## 1. 简介

### 1.1 文档目的

本文档详细说明股票历史数据接口的功能需求、技术实现要求、数据模型设计和验收标准，为开发团队提供明确的开发指南。

### 1.2 术语定义

| 术语       | 解释                                         |
| -------- | ------------------------------------------ |
| OHLC     | Open, High, Low, Close，分别表示开盘价、最高价、最低价、收盘价 |
| K线       | 股票价格走势图的一种表现形式，包含开盘价、最高价、最低价、收盘价           |
| SQLite   | 轻量级嵌入式数据库，用于本地存储历史数据                       |
| akshare  | 开源金融数据接口库，提供A股市场数据                         |
| yfinance | Yahoo Finance API，提供全球股票市场数据               |
| tushare  | 金融数据接口库，需要API密钥，提供A股市场数据                   |
| Upsert   | 插入或更新操作，当记录存在时更新，不存在时插入                    |

## 2. 功能需求

### 2.1 核心功能

#### 2.1.1 API 端点

* **端点**: `GET /api/v1/cn/equity/price/historical`

* **方法**: GET

* **功能**: 获取指定股票的历史价格数据（日K线）

#### 2.1.2 请求参数

| 参数名         | 类型     | 必填 | 默认值 | 说明                        |
| ----------- | ------ | -- | --- | ------------------------- |
| symbol      | string | 是  | -   | 股票代码（如 000001.SZ）         |
| start\_date | string | 否  | 一年前 | 开始日期 (YYYY-MM-DD)         |
| end\_date   | string | 否  | 今天  | 结束日期 (YYYY-MM-DD)         |
| interval    | string | 否  | 1d  | 时间间隔: 1d(日), 1w(周), 1m(月) |

#### 2.1.3 响应格式

```json
{
  "symbol": "000001.SZ",
  "interval": "1d",
  "data": [
    {
      "date": "2024-01-01",
      "open": 10.5,
      "high": 11.0,
      "low": 10.2,
      "close": 10.8,
      "volume": 1000000,
      "amount": 10500000
    }
  ],
  "source": "cache|akshare|yfinance|tushare",
  "cached_at": "2024-01-15T10:30:00Z"
}
```

### 2.2 数据获取流程

1. **查询本地数据库**：优先从本地缓存获取数据
2. **akshare**：当本地缓存未命中时，从 akshare 获取数据
3. **yfinance**：当 akshare 获取失败时，从 yfinance 获取数据
4. **tushare**：当 yfinance 获取失败时，从 tushare 获取数据
5. **返回错误**：当所有数据源都失败时，返回错误信息

### 2.3 数据源优先级

1. **本地缓存** - 优先返回已缓存的数据
2. **akshare** - 主要数据源，覆盖A股全市场
3. **yfinance** - 备用数据源，覆盖港股和美股
4. **tushare** - 最后备选，需要配置API密钥

## 3. 技术要求

### 3.1 技术栈

* **后端框架**: FastAPI

* **数据库**: SQLite

* **数据源**: akshare, yfinance, tushare

* **ORM**: 原生 SQLite3

* **缓存**: 本地 SQLite 数据库

### 3.2 数据库设计

#### 3.2.1 数据库位置

```python
from openbb_core.app.service.user_service import UserService
from pathlib import Path

# 读取用户设置
settings = UserService.read_from_file()
cache_dir = Path(settings.preferences.cache_directory)

# 在数据目录下创建SQLite数据库
db_path = cache_dir / "appdata/equity.db"
```

#### 3.2.2 表结构设计

**历史价格表 (equity\_price\_history)**

```sql
CREATE TABLE equity_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    interval TEXT NOT NULL DEFAULT '1d',
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    amount REAL,
    source TEXT DEFAULT 'akshare',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date, interval)
);

-- 复合索引：支持按股票查询历史和按日期范围查询
CREATE INDEX idx_price_symbol_date ON equity_price_history(symbol, date);
CREATE INDEX idx_price_date ON equity_price_history(date);
CREATE INDEX idx_price_interval ON equity_price_history(interval);
```

**元数据表 (equity\_metadata)**

```sql
CREATE TABLE equity_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT,
    market TEXT,
    list_date TEXT,
    last_fetched TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metadata_symbol ON equity_metadata(symbol);
```

### 3.3 增量更新策略

使用 `INSERT ... ON CONFLICT` 实现增量更新，确保数据的一致性和完整性。

### 3.4 性能优化

* **索引优化**：使用复合索引加速查询

* **SQLite 配置**：启用 WAL 模式、设置合适的缓存大小

* **查询优化**：使用参数化查询，避免 SQL 注入

### 3.5 错误处理

* **事务管理**：使用事务确保数据一致性

* **重试机制**：处理数据库锁定等临时错误

* **数据校验**：验证 OHLC 数据的逻辑一致性

* **日志记录**：记录所有操作和错误信息

## 4. 数据模型

### 4.1 价格数据模型

| 字段名         | 类型      | 说明                |
| ----------- | ------- | ----------------- |
| symbol      | string  | 股票代码              |
| date        | string  | 交易日期 (YYYY-MM-DD) |
| interval    | string  | 时间间隔 (1d, 1w, 1m) |
| open        | float   | 开盘价               |
| high        | float   | 最高价               |
| low         | float   | 最低价               |
| close       | float   | 收盘价               |
| volume      | integer | 成交量               |
| amount      | float   | 成交额               |
| source      | string  | 数据来源              |
| created\_at | string  | 创建时间              |
| updated\_at | string  | 更新时间              |

### 4.2 元数据模型

| 字段名           | 类型     | 说明     |
| ------------- | ------ | ------ |
| symbol        | string | 股票代码   |
| name          | string | 股票名称   |
| market        | string | 市场代码   |
| list\_date    | string | 上市日期   |
| last\_fetched | string | 最后获取时间 |
| created\_at   | string | 创建时间   |
| updated\_at   | string | 更新时间   |

## 5. 接口规范

### 5.1 请求示例

```
GET /api/v1/cn/equity/price/historical?symbol=000001.SZ&start_date=2024-01-01&end_date=2024-01-31&interval=1d
```

### 5.2 成功响应

```json
{
  "symbol": "000001.SZ",
  "interval": "1d",
  "data": [
    {
      "date": "2024-01-01",
      "open": 10.5,
      "high": 11.0,
      "low": 10.2,
      "close": 10.8,
      "volume": 1000000,
      "amount": 10500000
    },
    // 更多数据...
  ],
  "source": "akshare",
  "cached_at": "2024-01-15T10:30:00Z"
}
```

### 5.3 错误响应

```json
{
  "detail": "Failed to fetch data from all sources"
}
```

## 6. 验收标准

### 6.1 功能验收

* [ ] API 接口能正确响应 GET 请求

* [ ] 支持所有请求参数

* [ ] 返回格式符合规范

* [ ] 数据源优先级逻辑正确

* [ ] 缓存机制有效

### 6.2 性能验收

* [ ] 单条查询响应时间 < 10ms

* [ ] 批量写入 1000 条记录 < 100ms

* [ ] 1年历史数据范围查询 < 50ms

* [ ] 数据库大小 < 1GB（存储10年历史数据）

### 6.3 可靠性验收

* [ ] 数据源故障自动切换

* [ ] 数据库锁定自动重试

* [ ] 数据校验逻辑正确

* [ ] 错误处理机制有效

### 6.4 安全性验收

* [ ] 防止 SQL 注入

* [ ] 数据访问权限控制

* [ ] 敏感信息保护

## 7. 风险与依赖

### 7.1 风险

* **数据源依赖**：依赖外部数据源的稳定性和可用性

* **数据质量**：不同数据源的数据质量可能存在差异

* **性能瓶颈**：大量数据查询可能导致性能下降

* **存储限制**：SQLite 数据库大小限制

### 7.2 依赖

* **openbb**：核心金融数据接口库

* **openbb-akshare**：A股数据适配器

* **openbb-tushare**：Tushare 数据适配器

* **SQLite3**：本地数据库

* **FastAPI**：API 框架

## 8. 实施计划

### 8.1 开发阶段

1. **数据库模块**：实现数据库初始化、表结构创建和优化配置
2. **数据访问层**：实现数据查询、写入和增量更新
3. **数据源适配器**：实现各数据源的适配和优先级管理
4. **API 路由**：实现 API 端点和业务逻辑
5. **性能优化**：实现查询优化和数据库维护
6. **测试与文档**：编写测试用例和更新文档

### 8.2 测试计划

* **单元测试**：测试各个模块的功能

* **集成测试**：测试模块间的协作

* **性能测试**：测试接口响应时间和数据库性能

* **可靠性测试**：测试数据源故障切换和错误处理

## 9. 维护与监控

### 9.1 维护任务

* **定期维护**：每周执行数据库 VACUUM 操作

* **备份策略**：每月导出数据库文件

* **数据清理**：根据需要清理过期数据

### 9.2 监控指标

* **接口响应时间**：监控 API 响应时间

* **数据库性能**：监控数据库查询和写入性能

* **数据源可用性**：监控各数据源的可用性

* **错误率**：监控接口错误率

## 10. 总结

本规格说明文档详细描述了股票历史数据接口的功能需求、技术实现要求、数据模型设计和验收标准。通过本接口的实现，可以为用户提供稳定、高效、可靠的股票历史数据查询服务，支持多种数据源的自动切换，确保数据的及时性和准确性。
