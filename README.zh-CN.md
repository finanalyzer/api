# Finanalyzer API

> Finanalyzer 后端 API - 为个人用户打造的金融分析工作台

## 📖 项目简介

Finanalyzer API 是 Finanalyzer 项目的后端组件，是一个基于 Python / FastAPI 构建的金融分析 API。它完全兼容 OpenBB Workspace 架构标准，为个人用户提供更自由、更开放的选择。

后端利用 OpenBB Platform 进行数据获取，支持多种数据源，包括 AkShare、Tushare、通达信和 YFinance，实现全面的市场数据覆盖。

### 🎯 核心特性

- ✅ **完全开源** - 代码透明，自由定制
- ✅ **专注中国市场** - 原生支持 A 股和港股
- ✅ **多数据源** - AkShare、Tushare、通达信、YFinance 备用
- ✅ **投资组合管理** - 全面的股票和交易记录跟踪
- ✅ **仪表板 API** - 基于 Widget 的仪表板管理
- ✅ **AI 整合** - 支持 Claude Code / OpenCode 集成
- ✅ **Vibe-Trading 就绪** - 内置 AI 分析和回测支持

## 🏗️ 技术架构

Finanalyzer 后端采用与 OpenBB backends-for-openbb 相同的技术栈：

- **Python 3.13+** - 最新 Python 完整类型提示支持
- **FastAPI** - 高性能异步 API 框架
- **OpenBB Platform** - 官方数据平台集成
- **SQLite (WAL 模式)** - 轻量级持久化存储
- **uv** - 超快速 Python 包管理器
- **Pydantic** - 数据验证和配置管理

## 📦 安装指南

### 前置要求

- **Python**: 版本 3.13 或更高
- **uv**: uv 包管理器（推荐）
- **Git**: 版本 2.30 或更高
- **Docker**: （可选）用于容器化部署

验证环境：

```bash
# 检查 Python 版本
python --version  # 应 >= 3.13

# 检查 uv 版本（如已安装）
uv --version

# 检查 Git 版本
git --version
```

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/finanalyzer/api.git openbb-app
cd openbb-app
```

1. **安装依赖**

```bash
# 使用 uv（推荐）
uv pip install -e .

# 或使用 pip
pip install -e .
```

1. **配置环境变量**

在项目根目录创建 `.env` 文件：

```env
# Tushare API 密钥（可选，但推荐用于增强中国市场的数据）
TUSHARE_API_KEY=your_tushare_api_key_here

# Agent 主机 URL（可选，用于 AI 功能）
AGENT_HOST_URL=http://localhost:7778

# 应用 API 密钥（可选）
APP_API_KEY=your_app_api_key_here

# OpenRouter API 密钥（可选，用于 AI 功能）
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**环境变量说明**：

| 变量                   | 必需 | 说明                        |
| -------------------- | -- | ------------------------- |
| `TUSHARE_API_KEY`    | 否  | Tushare API 密钥（增强中国市场的数据） |
| `AGENT_HOST_URL`     | 否  | AI Agent 服务的 URL          |
| `APP_API_KEY`        | 否  | 用于认证的应用 API 密钥            |
| `OPENROUTER_API_KEY` | 否  | AI 功能的 OpenRouter API 密钥  |

**注意**：Tushare API 密钥可从 <https://tushare.pro/> 获取。虽然是可选的，但它提供了增强的中国市场数据。

1. **验证安装**

```bash
# 检查包是否已安装
uv pip list | grep openbb-app

# 运行帮助命令
openbb-app --help
```

## 🚀 快速开始

### 启动服务器

启动后端服务器：

```bash
# 使用已安装的脚本
openbb-app

# 或使用 uv
uv run openbb-app

# 或直接使用 uvicorn
uvicorn openbb_app.main:app --host 0.0.0.0 --port 8001 --reload
```

预期输出：

```
🚀 Starting OpenBB Backend on http://0.0.0.0:8001
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process [pid] using StatReload
openbb-app version: 1.5.7
```

### 访问 API 文档

服务器运行后，你可以访问交互式 API 文档：

- **Swagger UI**: <http://localhost:8001/api/docs>
- **Redoc**: <http://localhost:8001/api/redoc>
- **OpenAPI JSON**: <http://localhost:8001/api/openapi.json>

这两个文档界面让你可以：

- 探索所有 API 端点
- 直接在浏览器中试用 API 调用
- 查看请求/响应示例
- 查看 Pydantic 模型结构

### 测试健康检查

测试服务器是否正常运行：

```bash
# 使用 curl
curl http://localhost:8001/api/v1/health

# 使用 httpie
http http://localhost:8001/api/v1/health
```

预期响应：

```json
{
  "status": "healthy",
  "service": "openbb-app-builder-agent",
  ...
}
```

## 📚 API 端点概览

所有 API 端点前缀为 `/api/v1`。

### 健康检查

| 端点           | 方法  | 说明        |
| ------------ | --- | --------- |
| `/v1/health` | GET | 检查服务器是否健康 |

### 投资组合管理

| 端点                                | 方法     | 说明          |
| --------------------------------- | ------ | ----------- |
| `/v1/portfolio/stocks`            | GET    | 获取所有投资组合股票  |
| `/v1/portfolio/stocks/{symbol}`   | GET    | 按代码获取单个股票   |
| `/v1/portfolio/stocks`            | POST   | 添加新股票到投资组合  |
| `/v1/portfolio/stocks/{symbol}`   | PUT    | 更新投资组合中的股票  |
| `/v1/portfolio/stocks/{symbol}`   | DELETE | 从投资组合中移除股票  |
| `/v1/portfolio/transactions`      | GET    | 获取所有交易记录    |
| `/v1/portfolio/transactions/{id}` | GET    | 获取单个交易记录    |
| `/v1/portfolio/transactions`      | POST   | 添加新交易记录     |
| `/v1/portfolio/transactions/{id}` | PUT    | 更新交易记录      |
| `/v1/portfolio/transactions/{id}` | DELETE | 删除交易记录      |
| `/v1/portfolio/validate`          | GET    | 验证投资组合数据一致性 |

### 中国股票数据

| 端点                               | 方法  | 说明           |
| -------------------------------- | --- | ------------ |
| `/v1/cn/equity/price/historical` | GET | 获取历史价格数据     |
| `/v1/cn/equity/quote`            | GET | 获取实时报价（即将推出） |
| `/v1/cn/equity/search`           | GET | 搜索股票（即将推出）   |

### 仪表板管理

| 端点                                       | 方法     | 说明            |
| ---------------------------------------- | ------ | ------------- |
| `/v1/dashboard`                          | GET    | 获取所有仪表板       |
| `/v1/dashboard/{id}`                     | GET    | 获取单个仪表板       |
| `/v1/dashboard`                          | POST   | 创建新仪表板        |
| `/v1/dashboard/{id}`                     | PUT    | 更新仪表板         |
| `/v1/dashboard/{id}`                     | DELETE | 删除仪表板         |
| `/v1/dashboard/{id}/widgets`             | POST   | 向仪表板添加 Widget |
| `/v1/dashboard/{id}/widgets/{widget_id}` | PUT    | 更新 Widget     |
| `/v1/dashboard/{id}/widgets/{widget_id}` | DELETE | 删除 Widget     |

### AI Agent

| 端点                        | 方法   | 说明              |
| ------------------------- | ---- | --------------- |
| `/v1/agent/query`         | POST | 向 AI Agent 发送查询 |
| `/v1/agent/sessions`      | GET  | 获取聊天会话          |
| `/v1/agent/sessions/{id}` | GET  | 获取特定会话          |
| `/v1/agent/analyze`       | POST | 请求投资组合分析        |
| `/v1/agent/insights`      | GET  | 获取 AI 生成的洞察     |

### Widget 注册表

| 端点                 | 方法  | 说明              |
| ------------------ | --- | --------------- |
| `/v1/widgets.json` | GET | 获取所有已注册的 Widget |
| `/v1/apps.json`    | GET | 获取所有已注册的应用      |
| `/v1/agents.json`  | GET | 获取所有已注册的 Agent  |

## 🔐 认证

### 认证概述

openbb-app 后端使用灵活的认证系统：

- **无内置认证**：核心后端默认不需要认证
- **基于 Header 的认证**：支持自定义认证头
- **基于查询参数的认证**：支持通过 URL 参数认证
- **Cloudflare Access**：推荐用于生产部署

### 基于 Header 的认证

对于受 Cloudflare Access 保护的远程部署：

```python
import requests

headers = {
    "CF-Authorization": "your_cloudflare_access_token",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.yourcompany.com/api/v1/portfolio/stocks",
    headers=headers
)
```

### 基于查询参数的认证

通过 URL 参数进行简单认证：

```python
import requests

params = {
    "access_token": "your_access_token",
    "api_key": "your_api_key"
}

response = requests.get(
    "https://api.yourcompany.com/api/v1/portfolio/stocks",
    params=params
)
```

## 💻 集成示例

### 示例 1：获取投资组合股票

**Python (requests)**：

```python
import requests

BASE_URL = "http://localhost:8001"

response = requests.get(f"{BASE_URL}/api/v1/portfolio/stocks")

if response.status_code == 200:
    stocks = response.json()
    for stock in stocks:
        print(f"{stock['symbol']} - {stock['name']}: {stock['current_price']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

**cURL**：

```bash
curl -X GET http://localhost:8001/api/v1/portfolio/stocks \
  -H "Content-Type: application/json"
```

### 示例 2：添加交易记录

**Python (requests)**：

```python
import requests
from datetime import datetime

BASE_URL = "http://localhost:8001"

transaction = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "symbol": "000001.SZ",
    "name": "平安银行",
    "price": 16.20,
    "quantity": 50,
    "transaction_type": "买入",
    "total_value": 810.00
}

response = requests.post(
    f"{BASE_URL}/api/v1/portfolio/transactions",
    json=transaction
)

if response.status_code == 201:
    created = response.json()
    print(f"Transaction created: {created['id']}")
```

### 示例 3：获取历史价格数据

**Python (requests)**：

```python
import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8001"

end_date = datetime.now()
start_date = end_date - timedelta(days=90)

params = {
    "symbol": "000001.SZ",
    "start_date": start_date.strftime("%Y-%m-%d"),
    "end_date": end_date.strftime("%Y-%m-%d"),
    "interval": "1d"
}

response = requests.get(
    f"{BASE_URL}/api/v1/cn/equity/price/historical",
    params=params
)

if response.status_code == 200:
    data = response.json()
    print(f"Symbol: {data['symbol']}")
    print(f"Data points: {len(data['data'])}")
```

## 🐳 Docker 部署

### 前置要求

- 已安装 [Docker](https://docs.docker.com/get-docker/)
- 已安装 [Docker Compose](https://docs.docker.com/compose/install/)

### 快速开始

```bash
# 构建 Docker 镜像
docker build -t openbb-app .

# 启动服务（分离模式）
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

### 访问应用

容器运行后，可通过以下地址访问 API：

- API: <http://localhost:8001/api/docs>
- 健康检查: <http://localhost:8001/api/openapi.json>

### 环境配置

在项目根目录创建 `.env` 文件，配置你的 API 密钥：

```env
TUSHARE_API_KEY=your_tushare_api_key
AGENT_HOST_URL=your_agent_host_url
APP_API_KEY=your_app_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 热重载开发

Docker 配置支持热代码重载。对源代码的更改会立即反映，无需重新构建镜像。

### 容器安全

容器以非 root 用户（`appuser`）运行以增强安全性。应用在容器内监听 8001 端口，映射到主机的同一端口。

## 🛠️ 开发命令

```bash
# 以开发模式安装
uv pip install -e .

# 运行服务器
openbb-app

# 或使用 uvicorn
uvicorn openbb_app.main:app --host 0.0.0.0 --port 8001 --reload

# 运行测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_data_source.py

# 格式化代码
make format-backend
```

## 🔧 故障排除

### 常见问题

#### 问题 1：服务器无法启动

**症状**：

- 端口 8001 已被占用
- 启动时导入错误

**解决方案**：

1. 检查是否有其他进程使用该端口：
   ```bash
   # Windows
   netstat -ano | findstr :8001

   # Linux/Mac
   lsof -i :8001
   ```
2. 重新安装依赖：
   ```bash
   uv pip uninstall openbb-app
   uv pip install -e .
   ```

#### 问题 2：数据库错误

**症状**：

- SQLite 锁定错误
- WAL 模式警告

**解决方案**：

1. 确保只有一个实例在运行
2. 清除数据库：
   ```bash
   rm -f data/openbb.db
   ```

#### 问题 3：数据源失败

**症状**：

- 市场数据端点返回空响应
- 超时错误

**解决方案**：

1. 检查网络连接
2. 验证 API 密钥是否正确设置
3. 尝试备用数据源（AkShare、YFinance）
4. 检查 OpenBB Platform 状态

### 调试技巧

1. **启用详细日志**：
   ```bash
   openbb-app --verbose
   ```
2. **检查数据库内容**：
   ```bash
   sqlite3 data/openbb.db ".schema"
   ```
3. **直接测试 API 端点**：
   ```bash
   curl -v http://localhost:8001/api/v1/health
   ```

## 📦 发布到 PyPI

### 配置 uv 以使用 PyPI

将 PyPI 凭据添加到 `pyproject.toml`：

```toml
[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple/"
explicit = true
```

### 构建和发布

```bash
# 清除旧的构建
rm -rf dist/

# 构建分发包
uv build

# 发布到 PyPI
# 系统会提示你输入令牌（用户名：__token__）
uv publish
```

### 发布到 TestPyPI

```bash
# 将 TestPyPI 添加到 pyproject.toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true

# 构建并发布
uv build
uv publish --index testpypi

# 测试安装
uvx --index https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ openbb-app
```

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'feat: add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

### 代码风格

- 遵循 Black（行长度：88）+ isort（profile: "black"）
- 使用 `make format-backend` 自动格式化代码
- 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🔗 相关项目

- **Finanalyzer App (前端)**: <https://github.com/finanalyzer/app>
- **OpenBB Platform**: <https://github.com/OpenBB-finance/OpenBB>
- **AkShare**: <https://github.com/akfamily/akshare>
- **Tushare**: <https://tushare.pro/>

## 💬 支持

- **问题反馈**: [GitHub Issues](https://github.com/finanalyzer/api/issues)
- **功能建议**: [GitHub Discussions](https://github.com/finanalyzer/api/discussions)

***

> 投资有风险，分析需谨慎。本工具仅供研究学习使用。

