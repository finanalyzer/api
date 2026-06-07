# Finanalyzer API

> Finanalyzer Backend API - A Financial Analysis Workbench Built for Individual Users

## 📖 Project Overview

Finanalyzer API is the backend component of the Finanalyzer project, a high-performance financial analysis API built with Python / FastAPI. It fully complies with OpenBB Workspace architecture standards, providing individual users with a more flexible and open alternative.

The backend leverages the OpenBB Platform for data retrieval, supporting multiple data sources including AkShare, Tushare, TongDaXin (通达信), and YFinance for comprehensive market data coverage.

### 🎯 Core Features

- ✅ **Fully Open Source** - Transparent code, free customization
- ✅ **Chinese Market Focus** - Native support for A-shares and Hong Kong stocks
- ✅ **Multi-Source Data** - AkShare, Tushare, TongDaXin, YFinance fallback
- ✅ **Portfolio Management** - Comprehensive stock and transaction tracking
- ✅ **Dashboard API** - Widget-based dashboard management
- ✅ **AI Integration** - Claude Code / OpenCode integration support
- ✅ **Vibe-Trading Ready** - Built-in support for AI analysis and backtesting

## 🏗️ Technical Architecture

Finanalyzer backend adopts the same technology stack as OpenBB backends-for-openbb:

- **Python 3.13+** - Latest Python with full type hint support
- **FastAPI** - High-performance async API framework
- **OpenBB Platform** - Official data platform integration
- **SQLite (WAL mode)** - Lightweight persistent storage
- **uv** - Ultra-fast Python package manager
- **Pydantic** - Data validation and settings management

## 📦 Installation Guide

### Prerequisites

- **Python**: Version 3.13 or higher
- **uv**: uv package manager (recommended)
- **Git**: Version 2.30 or higher
- **Docker**: (Optional) For containerized deployment

Verify your environment:

```bash
# Check Python version
python --version  # Should be >= 3.13

# Check uv version (if installed)
uv --version

# Check Git version
git --version
```

### Installation Steps

1. **Clone the Repository**

```bash
git clone https://github.com/finanalyzer/api.git openbb-app
cd openbb-app
```

2. **Install Dependencies**

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

3. **Configure Environment Variables**

Create a `.env` file in the project root:

```env
# Tushare API key (optional but recommended for enhanced Chinese market data)
TUSHARE_API_KEY=your_tushare_api_key_here

# Agent host URL (optional, for AI features)
AGENT_HOST_URL=http://localhost:7778

# Application API key (optional)
APP_API_KEY=your_app_api_key_here

# OpenRouter API key (optional, for AI features)
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**Environment Variables**:

| Variable             | Required | Description                                       |
| -------------------- | -------- | ------------------------------------------------- |
| `TUSHARE_API_KEY`    | No       | API key for Tushare (enhanced Chinese market data) |
| `AGENT_HOST_URL`     | No       | URL for the AI agent service                      |
| `APP_API_KEY`        | No       | Application API key for authentication             |
| `OPENROUTER_API_KEY` | No       | OpenRouter API key for AI features                 |

**Note**: Tushare API key can be obtained from https://tushare.pro/. While optional, it provides enhanced data for Chinese markets.

4. **Verify Installation**

```bash
# Check that the package is installed
uv pip list | grep openbb-app

# Run the help command
openbb-app --help
```

## 🚀 Quick Start

### Starting the Server

Start the backend server:

```bash
# Using the installed script
openbb-app

# Or using uv
uv run openbb-app

# Or using uvicorn directly
uvicorn openbb_app.main:app --host 0.0.0.0 --port 8001 --reload
```

Expected output:

```
🚀 Starting OpenBB Backend on http://0.0.0.0:8001
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process [pid] using StatReload
openbb-app version: 1.5.7
```

### Accessing the API Documentation

Once the server is running, you can access the interactive API documentation:

- **Swagger UI**: http://localhost:8001/api/docs
- **Redoc**: http://localhost:8001/api/redoc
- **OpenAPI JSON**: http://localhost:8001/api/openapi.json

Both documentation interfaces let you:
- Explore all API endpoints
- Try out API calls directly from the browser
- View request/response examples
- See Pydantic model schemas

### Testing the Health Check

Test that the server is running correctly:

```bash
# Using curl
curl http://localhost:8001/api/v1/health

# Using httpie
http http://localhost:8001/api/v1/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "openbb-app-builder-agent",
  ...
}
```

## 📚 API Endpoints Overview

All API endpoints are prefixed with `/api/v1`.

### Health Check

| Endpoint         | Method | Description                        |
| ---------------- | ------ | ---------------------------------- |
| `/v1/health`     | GET    | Check if the server is healthy    |

### Portfolio Management

| Endpoint                       | Method | Description                         |
| ------------------------------ | ------ | ----------------------------------- |
| `/v1/portfolio/stocks`         | GET    | Get all portfolio stocks            |
| `/v1/portfolio/stocks/{symbol}`| GET    | Get a single stock by symbol        |
| `/v1/portfolio/stocks`         | POST   | Add a new stock to portfolio        |
| `/v1/portfolio/stocks/{symbol}`| PUT   | Update a stock in portfolio         |
| `/v1/portfolio/stocks/{symbol}`| DELETE | Remove a stock from portfolio       |
| `/v1/portfolio/transactions`   | GET    | Get all transaction records         |
| `/v1/portfolio/transactions/{id}`| GET  | Get a single transaction            |
| `/v1/portfolio/transactions`   | POST   | Add a new transaction               |
| `/v1/portfolio/transactions/{id}`| PUT  | Update a transaction                |
| `/v1/portfolio/transactions/{id}`| DELETE| Delete a transaction               |
| `/v1/portfolio/validate`        | GET    | Validate portfolio data consistency |

### Chinese Equity Data

| Endpoint                      | Method | Description                        |
| ----------------------------- | ------ | ---------------------------------- |
| `/v1/cn/equity/price/historical` | GET | Get historical price data          |
| `/v1/cn/equity/quote`         | GET    | Get real-time quotes (coming soon) |
| `/v1/cn/equity/search`        | GET    | Search for stocks (coming soon)    |

### Dashboard Management

| Endpoint                                   | Method | Description             |
| ------------------------------------------ | ------ | ----------------------- |
| `/v1/dashboard`                            | GET    | Get all dashboards      |
| `/v1/dashboard/{id}`                       | GET    | Get a single dashboard  |
| `/v1/dashboard`                           | POST   | Create a new dashboard  |
| `/v1/dashboard/{id}`                      | PUT    | Update a dashboard      |
| `/v1/dashboard/{id}`                      | DELETE | Delete a dashboard      |
| `/v1/dashboard/{id}/widgets`              | POST   | Add widget to dashboard |
| `/v1/dashboard/{id}/widgets/{widget_id}` | PUT    | Update widget           |
| `/v1/dashboard/{id}/widgets/{widget_id}` | DELETE | Delete widget           |

### AI Agents

| Endpoint               | Method | Description                |
| ---------------------- | ------ | -------------------------- |
| `/v1/agent/query`      | POST   | Send query to AI agent     |
| `/v1/agent/sessions`   | GET    | Get chat sessions          |
| `/v1/agent/sessions/{id}` | GET | Get specific session       |
| `/v1/agent/analyze`    | POST   | Request portfolio analysis |
| `/v1/agent/insights`   | GET    | Get AI-generated insights  |

### Widget Registry

| Endpoint          | Method | Description                |
| ----------------- | ------ | -------------------------- |
| `/v1/widgets.json` | GET    | Get all registered widgets |
| `/v1/apps.json`   | GET    | Get all registered apps    |
| `/v1/agents.json` | GET    | Get all registered agents  |

## 🔐 Authentication

### Authentication Overview

The openbb-app backend uses a flexible authentication system:

- **No Built-in Auth**: The core backend doesn't require authentication by default
- **Header-Based Auth**: Support for custom authentication headers
- **Query Parameter Auth**: Support for authentication via URL parameters
- **Cloudflare Access**: Recommended for production deployments

### Header-Based Authentication

For remote deployments protected by Cloudflare Access:

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

### Query Parameter Authentication

For simple authentication via URL parameters:

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

## 💻 Integration Examples

### Example 1: Fetch Portfolio Stocks

**Python (requests)**:

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

**cURL**:

```bash
curl -X GET http://localhost:8001/api/v1/portfolio/stocks \
  -H "Content-Type: application/json"
```

### Example 2: Add Transaction Record

**Python (requests)**:

```python
import requests
from datetime import datetime

BASE_URL = "http://localhost:8001"

transaction = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "symbol": "000001.SZ",
    "name": "Ping An Bank",
    "price": 16.20,
    "quantity": 50,
    "transaction_type": "buy",
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

### Example 3: Get Historical Price Data

**Python (requests)**:

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

## 🐳 Docker Deployment

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) installed

### Quick Start

```bash
# Build the Docker image
docker build -t openbb-app .

# Start the service (detached mode)
docker compose up -d

# View logs
docker compose logs -f

# Stop the service
docker compose down
```

### Accessing the Application

Once the container is running, access the API at:
- API: http://localhost:8001/api/docs
- Health Check: http://localhost:8001/api/openapi.json

### Environment Configuration

Create a `.env` file in the project root with your API keys:

```env
TUSHARE_API_KEY=your_tushare_api_key
AGENT_HOST_URL=your_agent_host_url
APP_API_KEY=your_app_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Development with Live Reload

The Docker setup supports live code reloading. Changes to source files on your host machine will be reflected immediately without rebuilding the image.

### Container Security

The container runs as a non-root user (`appuser`) for enhanced security. The application listens on port 8001 inside the container, which is mapped to the same port on the host.

## 🛠️ Development Commands

```bash
# Install in development mode
uv pip install -e .

# Run the server
openbb-app

# Or using uvicorn
uvicorn openbb_app.main:app --host 0.0.0.0 --port 8001 --reload

# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_data_source.py

# Format code
make format-backend
```

## 🔧 Troubleshooting

### Common Issues

#### Issue 1: Server Won't Start

**Symptoms**:
- Port 8001 already in use
- Import errors on startup

**Solutions**:

1. Check if another process is using the port:
   ```bash
   # Windows
   netstat -ano | findstr :8001
   
   # Linux/Mac
   lsof -i :8001
   ```

2. Reinstall dependencies:
   ```bash
   uv pip uninstall openbb-app
   uv pip install -e .
   ```

#### Issue 2: Database Errors

**Symptoms**:
- SQLite lock errors
- WAL mode warnings

**Solutions**:

1. Ensure only one instance is running
2. Clear the database:
   ```bash
   rm -f data/openbb.db
   ```

#### Issue 3: Data Source Failures

**Symptoms**:
- Empty responses from market data endpoints
- Timeout errors

**Solutions**:

1. Check network connectivity
2. Verify API keys are set correctly
3. Try an alternative data source (AkShare, YFinance)
4. Check OpenBB Platform status

### Debugging Tips

1. **Enable verbose logging**:
   ```bash
   openbb-app --verbose
   ```

2. **Check database contents**:
   ```bash
   sqlite3 data/openbb.db ".schema"
   ```

3. **Test API endpoints directly**:
   ```bash
   curl -v http://localhost:8001/api/v1/health
   ```

## 📦 Publishing to PyPI

### Configure `uv` for PyPI

Add your PyPI credentials to `pyproject.toml`:

```toml
[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple/"
explicit = true
```

### Build and Publish

```bash
# Clear old builds
rm -rf dist/

# Build the distribution
uv build

# Publish to PyPI
# You'll be prompted for a token (username: __token__)
uv publish
```

### Publishing to TestPyPI

```bash
# Add TestPyPI to pyproject.toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true

# Build and publish
uv build
uv publish --index testpypi

# Test installation
uvx --index https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ openbb-app
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork this repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'feat: add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Submit a Pull Request

### Code Style

- Follow Black (line length: 88) + isort (profile: "black")
- Use `make format-backend` to auto-format code
- Follow [Conventional Commits](https://www.conventionalcommits.org/) specification

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- **Finanalyzer App (Frontend)**: https://github.com/finanalyzer/app
- **OpenBB Platform**: https://github.com/OpenBB-finance/OpenBB
- **AkShare**: https://github.com/akfamily/akshare
- **Tushare**: https://tushare.pro/

## 💬 Support

- **Issue Tracker**: [GitHub Issues](https://github.com/finanalyzer/api/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/finanalyzer/api/discussions)

---

> Investment involves risks, analysis should be done carefully. This tool is for research and learning purposes only.
