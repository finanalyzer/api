# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Project Overview

A FastAPI-based financial data API server built on OpenBB platform, providing Chinese equity market data with multi-source fallback (AkShare, YFinance, Tushare), SQLite caching, and portfolio management capabilities.

**Version:** 0.4.9

## Build System & Commands

**Package Manager:** uv (with uv_build backend)

**Python Version:** 3.11+ (specified in `.python-version`)

### Common Commands

```bash
# Build the package
uv build

# Install the package in development mode
uv pip install -e .

# Run the API server (default port 8001)
openbb-app
# or
uv run openbb-app

# Alternative: run via openbb-api (port 6900 by default)
uv run openbb-api --app src/openbb_app/main.py

# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_data_source.py

# Run a specific test class or function
uv run pytest tests/test_data_source.py::TestNormalizeSymbolForYfinance
uv run pytest tests/test_data_source.py::TestNormalizeSymbolForYfinance::test_convert_shanghai_sh_to_ss
```

## Project Structure

```
openbb-app/
├── pyproject.toml              # Project configuration & dependencies
├── .python-version             # Python version (3.11)
├── src/openbb_app/
│   ├── __init__.py             # Package entry point
│   ├── main.py                 # FastAPI app & CLI entry point
│   ├── py.typed                # PEP 561 marker
│   ├── core/                   # Core modules
│   │   ├── __init__.py         # Exports DatabaseManager, DataSourceManager
│   │   ├── database.py         # SQLite database manager with WAL optimization
│   │   ├── data_source.py      # Multi-source data fetching (AkShare, YFinance, Tushare)
│   │   ├── agent.py            # Agent utilities
│   │   ├── auth.py             # Authentication
│   │   ├── config.py           # Configuration
│   │   ├── models.py           # Data models
│   │   ├── plotly_config.py    # Plotly visualization config
│   │   ├── registry.py         # Service registry
│   │   ├── session_manager.py  # Session management
│   │   ├── utils.py            # Utility functions
│   │   └── landing.html        # Landing page template
│   └── routes/                 # API routes
│       ├── __init__.py
│       ├── equity_cn.py        # Chinese equity market endpoints
│       └── portfolio.py        # Portfolio management endpoints
├── tests/                      # Test suite
│   ├── test_data_source.py     # Data source unit tests
│   └── test_portfolio.py       # Portfolio functionality tests
├── docs/                       # Documentation
│   ├── development.md          # Development guide
│   ├── openapi.json            # OpenAPI spec
│   └── usage.ipynb             # Usage examples
└── dist/                       # Build artifacts (gitignored)
```

## Architecture Notes

### Core Components

- **Build Backend:** Uses `uv_build` (>=0.9.7,<0.10.0)
- **Package Layout:** Follows src-layout convention (`src/openbb_app/`)
- **Type Safety:** Includes `py.typed` marker for PEP 561 compliance
- **API Framework:** FastAPI with uvicorn server (default port 8001)
- **Database:** SQLite with WAL mode, optimized for concurrent access

### Dual App Architecture

The application supports two modes controlled by the `using_openbb_api` flag in `main.py`:

1. **OpenBB Platform API mode** (default when `using_openbb_api=True`): Integrates with `openbb_platform_api` for enhanced platform features
2. **Standalone FastAPI mode** (`using_openbb_api=False`): Runs a standalone FastAPI app with CORS middleware for local development

The `get_app()` function returns the appropriate app instance based on this flag.

### Database Location

The database path is determined by OpenBB's user settings. The `get_db_manager()` function in `routes/equity_cn.py` reads the cache directory from `UserService.read_from_file()` and creates the database at `<cache_directory>/appdata/equity.db`.

### Data Sources (Priority Order)

The `DataSourceManager` tries sources in this order:

1. **AkShare** - Primary for A-share market (no API key required)
2. **YFinance** - Fallback for HK/US markets (no API key required)
3. **Tushare** - Last resort (requires `TUSHARE_API_KEY` environment variable)

## API Endpoints

### Health Check
- `GET /api/v1/health` - Health check endpoint

### Chinese Equity Market (`/api/v1/cn`)
- `GET /equity/price/historical` - Historical price data for Chinese stocks
  - Query params: `symbol`, `start_date`, `end_date`, `interval`

### Portfolio Management (`/api/v1`)
- `GET /portfolio/stocks` - Get all portfolio stocks
- `GET /portfolio/stocks/{symbol}` - Get single portfolio stock
- `POST /portfolio/stocks` - Create new portfolio stock
- `PUT /portfolio/stocks/{symbol}` - Update portfolio stock
- `DELETE /portfolio/stocks/{symbol}` - Delete portfolio stock
- `GET /portfolio/transactions` - Get all transactions (with optional filters)
- `GET /portfolio/transactions/{id}` - Get single transaction
- `POST /portfolio/transactions` - Create new transaction
- `PUT /portfolio/transactions/{id}` - Update transaction
- `DELETE /portfolio/transactions/{id}` - Delete transaction
- `GET /portfolio/validate` - Validate portfolio data consistency

### Dashboard Management (`/api/v1`)
- `GET /dashboard` - Get all dashboards
- `GET /dashboard/{dashboard_id}` - Get single dashboard
- `POST /dashboard` - Create new dashboard
- `PUT /dashboard/{dashboard_id}` - Update dashboard
- `DELETE /dashboard/{dashboard_id}` - Delete dashboard
- `GET /dashboard/{dashboard_id}/widgets` - Get all widgets in a dashboard
- `POST /dashboard/{dashboard_id}/widgets` - Add widget to dashboard
- `PUT /dashboard/{dashboard_id}/widgets/{widget_id:path}` - Update widget (uses `:path` converter for IDs with slashes)
- `DELETE /dashboard/{dashboard_id}/widgets/{widget_id:path}` - Delete widget (uses `:path` converter for IDs with slashes)

## Database Schema

### equity_price_history table
- Stores OHLC data with symbol, date, interval
- Uses UPSERT for incremental updates
- Indexed on (symbol, date), (date), (interval)

### equity_metadata table
- Stores stock metadata (name, market, list_date)
- Indexed on symbol

### portfolio_stocks table
- Stores portfolio stock information
- Fields: symbol (PK), name, avg_cost, quantity, total_value
- Note: Financial metrics are now retrieved dynamically using obb.equity.price.quote

### transactions table
- Stores transaction records
- Fields: id (PK), date, symbol, name, price, quantity, transaction_type
- Foreign key to portfolio_stocks (ON DELETE CASCADE)
- Indexed on symbol, date

## Key Dependencies

```toml
[project]
dependencies = [
    "mysharelib>=1.0.4",      # Symbol normalization utilities
    "openbb>=4.6.0",          # OpenBB platform core
    "openbb-ai>=1.8.7",       # AI integration
    "openbb-akshare>=1.1.3",  # A-share data provider
    "openbb-tushare>=1.0.0",  # Tushare data provider
    "uvicorn>=0.40.0",        # ASGI server
]

[dependency-groups]
dev = [
    "ipykernel>=6.30.1",      # Jupyter kernel
    "pytest>=9.0.2",          # Testing framework
]
```

## Environment Variables

Required for full functionality (set in `.env` file):

- `TUSHARE_API_KEY` - Tushare API key for Chinese market data
- `AGENT_HOST_URL` - Agent host URL for AI features
- `APP_API_KEY` - Application API key
- `OPENROUTER_API_KEY` - OpenRouter API key

## CLI Entry Points

Two scripts are defined in `pyproject.toml`:

- `openbb-app` - Starts the API server (main entry point)
- `openbb-update` - Updates equity data (see `src/openbb_app/update_equity_data.py`)

## Development Guidelines

### Adding New API Endpoints

1. Create router in `src/openbb_app/routes/`
2. Import and include router in `main.py`
3. Use `DatabaseManager` for cached data access
4. Use `DataSourceManager` for fetching from external sources

### Data Source Pattern

```python
from openbb_app.core import DatabaseManager, DataSourceManager

db_manager = DatabaseManager(db_path)
data_source_manager = DataSourceManager()

# Try cache first
cached = db_manager.get_price_data(symbol, start, end, interval)

# If miss, fetch from sources
if not cached:
    data, source = data_source_manager.get_data(symbol, start, end, interval)
    db_manager.upsert_price_data(symbol, data, source)
```

### Portfolio Transaction Pattern

```python
from openbb_app.core import DatabaseManager

db_manager = DatabaseManager(db_path)

# Add a buy transaction (auto-updates portfolio data)
transaction = {
    'date': '2024-01-01',
    'symbol': '000001.SZ',
    'name': '平安银行',
    'price': 15.0,
    'quantity': 100,
    'transaction_type': '买入'
}
db_manager.add_transaction(transaction)

# Validate data consistency
result = db_manager.validate_portfolio_data()
```

**Important:** When adding/updating/deleting transactions, `DatabaseManager` automatically recalculates the portfolio stock's `avg_cost`, `quantity`, and `total_value` via `_update_portfolio_data()`. The average cost is calculated using the total buy value (including transaction fees), not just price × quantity.

### Portfolio Stocks Dynamic Data Pattern

```python
from openbb_app.core import DatabaseManager, get_stock_quote, get_strategies, get_tvlink

db_manager = DatabaseManager(db_path)

# Get portfolio stocks with dynamically retrieved data
stocks = db_manager.get_all_portfolio_stocks()
# Each stock will include:
# - Stored fields: symbol, name, avg_cost, quantity, total_value
# - Dynamically retrieved: current_price, fifty_two_week_low, fifty_two_week_high, dividend_yield, latest_dividend
# - Calculated: strategy, tradingview

# Get single stock with dynamic data
stock = db_manager.get_portfolio_stock('000001.SZ')
```

**Important:** Financial metrics are now retrieved dynamically using `obb.equity.price.quote` and cached temporarily. The `strategy` field is calculated based on average cost and current price, while the `tradingview` field is generated as a direct link to TradingView.

### Symbol Format

- A-share stocks: `000001.SZ`, `600000.SH`
- Hong Kong stocks: `00700.HK`
- Symbol normalization handled by `mysharelib.tools.normalize_symbol`

## Testing

- Run `uv run pytest` to execute all tests
- Tests use temporary databases for isolation
- See `tests/test_data_source.py` for data source tests
- See `tests/test_portfolio.py` for portfolio functionality tests

## Code Style

- Uses `py.typed` marker for PEP 561 type hint compliance
- Logging via standard `logging` module with `mysharelib.tools.setup_logger`
- Pydantic models for request/response validation in API routes

## Path Parameter Notes

### Widget IDs with Slashes

Widget IDs may contain forward slashes (e.g., `equity/screener-1776216985149-eznmq1p30wq`). To handle these correctly in FastAPI routes, use the `:path` converter:

```python
# Correct - captures everything including slashes
@dashboard_router.delete("/dashboard/{dashboard_id}/widgets/{widget_id:path}")

# Incorrect - will not match widget IDs containing slashes
@dashboard_router.delete("/dashboard/{dashboard_id}/widgets/{widget_id}")
```

The `:path` converter is a Starlette feature that captures the entire remaining path segment, including forward slashes. This is essential for widget management endpoints since widget IDs are generated from the original widget type (e.g., `equity/screener`).
