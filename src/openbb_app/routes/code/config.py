"""Configuration for OpenBB App Builder Agent."""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Agent configuration settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 7778

    # Target workspace repo (where .claude skills live)
    target_repo_path: Optional[str] = None

    # Session management
    session_dir: str = ".agent_sessions"
    session_ttl_hours: int = 24

    # Claude CLI settings
    claude_binary: Optional[str] = None
    claude_timeout: float = 600.0  # 10 minutes for app builds
    claude_skip_permissions: bool = True

    # OpenCode CLI settings
    opencode_binary: Optional[str] = None
    opencode_timeout: float = 600.0
    opencode_default_port: int = 4096
    default_model: str = "opencode/deepseek-v4-flash-free"

    # Logging
    log_level: str = "INFO"

    # Code generator settings
    code_generator: str = "claude"

    model_config = {
        "env_prefix": "OPENBB_APP_BUILDER_",
        "env_file": ".env",
        "extra": "ignore",
    }

    @property
    def resolved_target_repo(self) -> Optional[Path]:
        """Get resolved target repo path."""
        if self.target_repo_path:
            path = Path(self.target_repo_path).expanduser().resolve()
            if path.exists():
                return path
        return None

    @property
    def resolved_session_dir(self) -> Path:
        """Get resolved session directory path."""
        if self.resolved_target_repo:
            return self.resolved_target_repo / self.session_dir
        return Path(self.session_dir).resolve()


# Global settings instance
settings = Settings()


def find_claude_binary() -> Optional[str]:
    """Find the Claude Code CLI binary.

    Returns:
        Path to claude binary if found, None otherwise.
    """
    import shutil

    # Check configured path first
    if settings.claude_binary:
        if os.path.isfile(settings.claude_binary) and os.access(
            settings.claude_binary, os.X_OK
        ):
            return settings.claude_binary

    # Check if claude is in PATH
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    # Check common installation locations
    common_paths = [
        os.path.expanduser("~/.claude/bin/claude"),
        "/usr/local/bin/claude",
        "/opt/homebrew/bin/claude",
    ]

    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


def check_claude_installed() -> tuple[bool, str]:
    """Check if Claude Code CLI is installed and accessible.

    Returns:
        Tuple of (is_installed, message).
    """
    binary = find_claude_binary()
    if binary:
        return True, f"Claude Code CLI found at: {binary}"
    return False, (
        "Claude Code CLI not found. Please install it from: "
        "https://docs.anthropic.com/en/docs/claude-code"
    )


OPENCODE_DEFAULT_PORT = 4096


def find_opencode_binary() -> Optional[str]:
    """Find the OpenCode CLI binary.

    Returns:
        Path to opencode binary if found, None otherwise.
    """
    import shutil

    if settings.opencode_binary:
        if os.path.isfile(settings.opencode_binary) and os.access(
            settings.opencode_binary, os.X_OK
        ):
            return settings.opencode_binary

    opencode_path = shutil.which("opencode")
    if opencode_path:
        return opencode_path

    common_paths = [
        os.path.expanduser("~/.opencode/bin/opencode"),
        os.path.expanduser("~/.local/bin/opencode"),
        os.path.expanduser("~/go/bin/opencode"),
        "/usr/local/bin/opencode",
        "/opt/homebrew/bin/opencode",
    ]

    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


def check_opencode_installed() -> tuple[bool, str]:
    """Check if OpenCode CLI is installed and accessible.

    Returns:
        Tuple of (is_installed, message).
    """
    binary = find_opencode_binary()
    if binary:
        return True, f"OpenCode CLI found at: {binary}"
    return False, (
        "OpenCode CLI not found. Please install it from: https://opencode.ai"
    )


def check_target_repo() -> tuple[bool, str]:
    """Check if target repo is configured and exists.

    Returns:
        Tuple of (exists, message).
    """
    if not settings.target_repo_path:
        return (
            False,
            "Target repo not configured (set OPENBB_APP_BUILDER_TARGET_REPO_PATH)",
        )

    path = settings.resolved_target_repo
    if path and path.exists():
        # Check for .claude directory
        claude_dir = path / ".claude"
        if claude_dir.exists():
            return True, f"Target repo found at: {path} (with .claude skills)"
        return True, f"Target repo found at: {path} (no .claude directory)"

    return False, f"Target repo not found at: {settings.target_repo_path}"
