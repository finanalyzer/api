# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

A minimal Python package scaffold using `uv` as the build system and package manager.

## Build System & Commands

**Package Manager:** uv (with uv_build backend)

**Python Version:** 3.11+ (specified in `.python-version`)

### Common Commands

```bash
# Build the package
uv build

# Install the package in development mode
uv pip install -e .

# Run tests (no test framework configured yet)
# Add pytest or preferred framework as needed

# Lint/type-check (not configured yet)
# Add ruff, mypy, or preferred tools as needed
```

## Project Structure

```
openbb-app/
├── pyproject.toml      # Project configuration & build system
├── .python-version     # Python version specification (3.11)
├── src/openbb_app/     # Package source
│   ├── __init__.py     # Package entry point
│   └── py.typed        # PEP 561 marker for type checking support
└── dist/               # Build artifacts (gitignored)
```

## Architecture Notes

- **Build Backend:** Uses `uv_build` (>=0.9.7,<0.10.0) as specified in `pyproject.toml`
- **Package Layout:** Follows src-layout convention (`src/openbb_app/`)
- **Type Safety:** Includes `py.typed` marker for PEP 561 compliance
- **No Dependencies:** Currently has no external dependencies listed in `pyproject.toml`

## Key Configuration

The `pyproject.toml` is the single source of truth for:
- Project metadata (name, version, description, authors)
- Python version requirement (>=3.11)
- Build system configuration
- Dependencies (currently empty)
