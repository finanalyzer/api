---
name: app-builder
description: This is a skill for the development of OpenBB app builder.
---

# OpenBB App Builder Agent Skill

## Overview

The **OpenBB App Builder Agent** is a specialized integration that bridges OpenBB Copilot with OpenCode CLI or Claude Code CLI, enabling automated generation of OpenBB Workspace backend applications. This skill provides a robust API for building production-ready FastAPI backends with widget endpoints.

## Supported Code Generators

### Claude Code CLI
- **Binary Detection**: Automatically finds Claude Code binary in system PATH
- **Session Management**: Supports both new sessions and continued sessions using session IDs
- **Output Format**: Uses `--output-format stream-json` for structured event streaming
- **Features**:
  - Chrome browser integration via `--chrome` flag
  - Permission skipping with `--dangerously-skip-permissions`
  - Verbose output for detailed logging
  - Configurable timeout (default: 600 seconds)
  - 10MB buffer limit for large outputs (e.g., screenshots)
  - Process locking to prevent concurrent executions

### OpenCode
- **Binary Detection**: Searches for `opencode` binary in PATH and common installation locations:
  - `~/.opencode/bin/opencode`
  - `/usr/local/bin/opencode`
  - `/opt/homebrew/bin/opencode`
- **Command**: Runs with `opencode run <prompt>`
- **Features**:
  - JSON and non-JSON output parsing
  - Configurable timeout (default: 600 seconds)
  - 10MB buffer limit
  - Process locking for safety

## Configuration

Both generators support:
- `working_directory`: Optional working directory (defaults to current directory or target repo)
- `timeout`: Execution timeout in seconds (default: 600.0)
- `skip_permissions`: Skip permission prompts (Claude only, default: True)

## Event Streaming

The app builder streams parsed events including:
- `reasoning_step`: System events (INFO, WARNING, ERROR) with structured details
- `message_chunk`: Text output chunks for real-time feedback
- Error handling with user-friendly messages
- Stderr capture and reporting

## Session Management

- Session IDs for tracking execution context
- Support for session continuation (`--resume` flag)
- Process locking via session_manager to prevent concurrent executions
- Automatic cleanup on completion or error

## Error Handling

Comprehensive error handling for:
- Binary not found
- Permission denied
- Execution timeouts (with graceful termination)
- JSON parsing errors
- Unexpected exceptions with detailed logging