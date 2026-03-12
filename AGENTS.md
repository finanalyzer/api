# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

A FastAPI-based financial data API server built on OpenBB platform, providing Chinese equity market data with multi-source fallback (AkShare, YFinance, Tushare) and SQLite caching.

## Build System & Commands

**Package Manager:** uv (with uv_build backend)

**Python Version:** 3.11+ (specified in `.python-version`)

### Common Commands

```bash
# Build the package
uv build

# Install the package in development mode
uv pip install -e .

# Run the API server
openbb-app
# or
uv run openbb-app

# Run tests
uv run pytest

# Run tests with verbose output
uv run pytest -v
```

## Project Structure

```
openbb-app/
├── pyproject.toml          # Project configuration & dependencies
├── .python-version         # Python version (3.11)
├── src/openbb_app/
│   ├── __init__.py         # Package entry point
│   ├── main.py             # FastAPI app & CLI entry point
│   ├── py.typed            # PEP 561 marker
│   ├── core/               # Core modules
│   │   ├── __init__.py     # Exports DatabaseManager, DataSourceManager
│   │   ├── database.py     # SQLite database manager with WAL optimization
│   │   ├── data_source.py  # Multi-source data fetching (AkShare, YFinance, Tushare)
│   │   ├── agent.py        # Agent utilities
│   │   ├── auth.py         # Authentication
│   │   ├── config.py       # Configuration
│   │   ├── models.py       # Data models
│   │   ├── plotly_config.py
│   │   ├── registry.py
│   │   ├── session_manager.py
│   │   └── utils.py
│   ├── routes/             # API routes
│   │   ├── __init__.py
│   │   └── equity_cn.py    # Chinese equity market endpoints
│   └── cache/              # Cache storage
│       └── appdata/        # SQLite database location
├── tests/                  # Test suite
│   └── test_data_source.py # Data source unit tests
├── docs/                   # Documentation
│   ├── development.md      # Development guide
│   ├── openapi.json        # OpenAPI spec
│   └── usage.ipynb         # Usage examples
└── dist/                   # Build artifacts (gitignored)
```

## Architecture Notes

### Core Components

- **Build Backend:** Uses `uv_build` (>=0.9.7,<0.10.0)
- **Package Layout:** Follows src-layout convention (`src/openbb_app/`)
- **Type Safety:** Includes `py.typed` marker for PEP 561 compliance
- **API Framework:** FastAPI with uvicorn server
- **Database:** SQLite with WAL mode, optimized for concurrent access

### Data Sources (Priority Order)

1. **Tushare** - Primary source (requires API key)
2. **YFinance** - Fallback for HK/US markets
3. **AkShare** - Fallback for A-share market

### API Endpoints

- `GET /api/v1/health` - Health check
- `GET /api/v1/cn/equity/price/historical` - Historical price data for Chinese stocks

### Database Schema

**equity_price_history table:**
- Stores OHLC data with symbol, date, interval
- Uses UPSERT for incremental updates
- Indexed on (symbol, date), (date), (interval)

**equity_metadata table:**
- Stores stock metadata (name, market, list_date)
- Indexed on symbol

## Key Dependencies

```toml
dependencies = [
    "mysharelib>=1.0.4",      # Symbol normalization utilities
    "openbb>=4.7.0",          # OpenBB platform core
    "openbb-akshare>=1.0.5",  # A-share data provider
    "openbb-tushare>=1.0.0",  # Tushare data provider
    "uvicorn>=0.40.0",        # ASGI server
]

[dependency-groups]
dev = [
    "pytest>=9.0.2",          # Testing framework
]
```

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

### Symbol Format

- A-share stocks: `000001.SZ`, `600000.SH`
- Hong Kong stocks: `00700.HK`
- Symbol normalization handled by `mysharelib.tools.normalize_symbol`

## Testing

- Run `uv run pytest` to execute all tests
- Tests use mocking for external dependencies
- See `tests/test_data_source.py` for examples