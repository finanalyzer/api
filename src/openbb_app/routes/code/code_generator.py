"""Code generator abstract base class and implementations."""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional

import httpx
from openbb_ai import message_chunk, reasoning_step

from .config import (
    OPENCODE_DEFAULT_PORT,
    check_opencode_installed,
    find_opencode_binary,
    settings,
)
from .session_manager import Session, session_manager


@dataclass
class ModelInfo:
    """Information about an available LLM model."""

    id: str
    name: str
    provider: str


class CodeGeneratorConfig:
    """Base configuration for code generators."""

    def __init__(
        self,
        working_directory: Optional[str] = None,
        timeout: float = 600.0,
        **kwargs,
    ):
        """Initialize configuration."""
        self.working_directory = working_directory
        self.timeout = timeout
        self.kwargs = kwargs


class CodeGenerator(ABC):
    """Abstract base class for code generators."""

    @abstractmethod
    async def run(
        self, prompt: str, session: Session, config: CodeGeneratorConfig
    ) -> AsyncGenerator[dict, None]:
        """Run code generation with the given prompt."""
        pass

    @abstractmethod
    def check_availability(self) -> tuple[bool, str]:
        """Check if the code generator is available."""
        pass

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List available models for this code generator."""
        pass


@dataclass
class OpenCodeRunnerConfig:
    """Configuration for OpenCode invocation."""

    working_directory: Optional[str] = None
    timeout: float = 600.0
    port: int = OPENCODE_DEFAULT_PORT
    model_id: Optional[str] = None


_opencode_server_process: Optional[asyncio.subprocess.Process] = None

logger = logging.getLogger(__name__)


async def ensure_opencode_server(config: OpenCodeRunnerConfig) -> tuple[bool, str]:
    """Ensure OpenCode server is running.

    Returns:
        Tuple of (success, base_url_or_error_message)
    """
    global _opencode_server_process

    base_url = f"http://127.0.0.1:{config.port}"

    async def check_server() -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/global/health")
                return resp.status_code == 200
        except Exception:
            return False

    if await check_server():
        logger.info(f"OpenCode server already running at {base_url}")
        return True, base_url

    opencode_binary = find_opencode_binary()
    if not opencode_binary:
        return False, "OpenCode CLI not found. Please install from https://opencode.ai"

    cwd = config.working_directory
    if not cwd and settings.resolved_target_repo:
        cwd = str(settings.resolved_target_repo)
    if not cwd:
        cwd = os.getcwd()

    logger.info(f"Starting OpenCode server on port {config.port} in {cwd}")

    cmd = [
        opencode_binary,
        "serve",
        "--port",
        str(config.port),
        "--hostname",
        "127.0.0.1",
    ]

    _opencode_server_process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    for i in range(30):
        await asyncio.sleep(0.5)
        if await check_server():
            logger.info(f"OpenCode server started at {base_url}")
            return True, base_url
        if _opencode_server_process.returncode is not None:
            stderr = ""
            if _opencode_server_process.stderr:
                stderr = (await _opencode_server_process.stderr.read()).decode()
            logger.error(f"OpenCode server failed: {stderr}")
            return False, f"OpenCode server failed to start: {stderr[:500]}"

    return False, "OpenCode server startup timed out"


def format_tool_message(tool_name: str, tool_input: dict) -> str:
    """Generate a human-readable message describing a tool execution."""
    name_lower = tool_name.lower()

    if name_lower in ("read", "view"):
        path = tool_input.get("file_path", "")
        return f"Reading file: {path.split('/')[-1] if path else 'unknown'}"

    if name_lower == "write":
        path = tool_input.get("file_path", "")
        return f"Creating file: {path.split('/')[-1] if path else 'unknown'}"

    if name_lower == "edit":
        path = tool_input.get("file_path", "")
        return f"Editing file: {path.split('/')[-1] if path else 'unknown'}"

    if name_lower == "bash":
        cmd = tool_input.get("command", "")
        return f"Running: {cmd[:50]}..." if len(cmd) > 50 else f"Running: {cmd}"

    if name_lower == "glob":
        pattern = tool_input.get("pattern", "")
        return f"Searching for files: {pattern}"

    if name_lower == "grep":
        pattern = tool_input.get("pattern", "")
        return f"Searching for: {pattern[:30]}..."

    return f"Executing: {tool_name}"


class ClaudeCodeGenerator(CodeGenerator):
    """Claude Code CLI generator implementation."""

    # Known Claude Code models (updated May 2026)
    CLAUDE_MODELS: List[ModelInfo] = [
        ModelInfo(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            provider="anthropic",
        ),
        ModelInfo(
            id="claude-opus-4-20250514",
            name="Claude Opus 4",
            provider="anthropic",
        ),
        ModelInfo(
            id="claude-haiku-3-5-20241022",
            name="Claude 3.5 Haiku",
            provider="anthropic",
        ),
    ]

    async def run(
        self, prompt: str, session: Session, config: CodeGeneratorConfig
    ) -> AsyncGenerator[Dict, None]:
        """Run Claude Code CLI."""
        from .claude_runner import ClaudeRunnerConfig, run_claude_code

        # Convert to Claude-specific config
        claude_config = ClaudeRunnerConfig(
            working_directory=config.working_directory,
            timeout=config.timeout,
            skip_permissions=config.kwargs.get("skip_permissions", True),
        )

        async for event in run_claude_code(prompt, session, claude_config):
            yield event.data

    def check_availability(self) -> tuple[bool, str]:
        """Check if Claude Code CLI is available."""
        from .config import check_claude_installed

        return check_claude_installed()

    async def list_models(self) -> List[ModelInfo]:
        """List available Claude Code models.

        Claude Code CLI doesn't have a programmatic "list models" endpoint.
        Returns a curated list of known models, augmented with the user's
        configured model from ~/.claude/settings.json if available.
        """
        models = list(self.CLAUDE_MODELS)

        # Try to read the user's configured model from Claude settings
        try:
            import json
            from pathlib import Path

            settings_path = Path.home() / ".claude" / "settings.json"
            if settings_path.exists():
                settings_data = json.loads(settings_path.read_text())
                configured_model = settings_data.get("model")
                if configured_model and not any(
                    m.id == configured_model for m in models
                ):
                    models.append(
                        ModelInfo(
                            id=configured_model,
                            name=configured_model,
                            provider="anthropic",
                        )
                    )
        except Exception:
            pass  # Silently ignore settings read failures

        return models


class OpenCodeGenerator(CodeGenerator):
    """OpenCode generator implementation."""

    async def run(
        self, prompt: str, session: Session, config: CodeGeneratorConfig
    ) -> AsyncGenerator[dict, None]:
        """Run OpenCode via HTTP API and stream parsed events."""
        opencode_config = OpenCodeRunnerConfig(
            working_directory=config.working_directory,
            timeout=config.timeout,
            port=settings.opencode_default_port,
            model_id=settings.default_model,
        )

        server_ok, server_result = await ensure_opencode_server(opencode_config)
        if not server_ok:
            yield reasoning_step(
                event_type="ERROR",
                message="OpenCode server unavailable",
                details={"error": server_result},
            ).model_dump()
            return

        base_url = server_result
        opencode_session_id = session.opencode_session_id

        yield reasoning_step(
            event_type="INFO",
            message="Starting OpenCode execution",
            details={
                "session_id": session.session_id,
                "opencode_session_id": opencode_session_id,
                "continued": session.is_continued,
            },
        ).model_dump()

        try:
            await session_manager.acquire_process_lock()

            async with httpx.AsyncClient(timeout=config.timeout) as client:

                async def _create_new_session() -> Optional[str]:
                    """Create a fresh OpenCode session, returning its ID or None on failure."""
                    create_resp = await client.post(
                        f"{base_url}/session", json={"modelID": settings.default_model}
                    )
                    if create_resp.status_code != 200:
                        return None
                    return create_resp.json().get("id")

                if opencode_session_id:
                    try:
                        check_resp = await client.get(
                            f"{base_url}/session/{opencode_session_id}",
                            timeout=5.0,
                        )
                        if check_resp.status_code != 200:
                            logger.warning(
                                f"Cached OpenCode session {opencode_session_id} "
                                f"no longer exists (HTTP {check_resp.status_code}). "
                                "Creating a new session."
                            )
                            opencode_session_id = None
                    except Exception as check_err:
                        logger.warning(
                            f"Could not validate cached session: {check_err}. "
                            "Creating a new session."
                        )
                        opencode_session_id = None

                if not opencode_session_id:
                    opencode_session_id = await _create_new_session()
                    if not opencode_session_id:
                        yield reasoning_step(
                            event_type="ERROR",
                            message="Failed to create OpenCode session",
                            details={},
                        ).model_dump()
                        return
                    session.opencode_session_id = opencode_session_id
                    logger.info(f"Created OpenCode session: {opencode_session_id}")

                yield reasoning_step(
                    event_type="INFO",
                    message="Sending message to OpenCode...",
                    details={},
                ).model_dump()

                message_resp = await client.post(
                    f"{base_url}/session/{opencode_session_id}/message",
                    json={
                        "parts": [{"type": "text", "text": prompt}],
                    },
                )

                if message_resp.status_code != 200:
                    yield reasoning_step(
                        event_type="ERROR",
                        message="Failed to send message",
                        details={
                            "status": message_resp.status_code,
                            "error": message_resp.text[:500],
                        },
                    ).model_dump()
                    return

                message_data = message_resp.json()
                parts = message_data.get("parts", [])

                logger.info(f"Received response with {len(parts)} parts")

                for part in parts:
                    part_type = part.get("type", "")

                    if part_type == "text":
                        text = part.get("text", "")
                        if text:
                            yield message_chunk(text).model_dump()

                    elif part_type == "tool_use":
                        tool_name = part.get("name", "unknown")
                        tool_input = part.get("input", {})

                        msg = format_tool_message(tool_name, tool_input)
                        details = {"tool": tool_name}
                        if tool_input:
                            input_str = json.dumps(tool_input)
                            if len(input_str) > 300:
                                input_str = input_str[:300] + "..."
                            details["input"] = input_str

                        yield reasoning_step(
                            event_type="INFO",
                            message=msg,
                            details=details,
                        ).model_dump()

                    elif part_type == "tool_result":
                        content = part.get("content", "")
                        is_error = part.get("is_error", False)

                        if isinstance(content, str) and len(content) > 500:
                            display_content = content[:500] + "..."
                        else:
                            display_content = str(content)[:500]

                        yield reasoning_step(
                            event_type="ERROR" if is_error else "INFO",
                            message="Tool failed" if is_error else "Tool completed",
                            details={"output": display_content},
                        ).model_dump()

                yield reasoning_step(
                    event_type="INFO",
                    message="OpenCode completed successfully",
                    details={},
                ).model_dump()

        except httpx.TimeoutException:
            yield reasoning_step(
                event_type="ERROR",
                message="Request timed out",
                details={"timeout_seconds": config.timeout},
            ).model_dump()
        except httpx.ConnectError as e:
            yield reasoning_step(
                event_type="ERROR",
                message="Failed to connect to OpenCode server",
                details={"error": str(e)},
            ).model_dump()
        except Exception as e:
            logger.exception("Unexpected error in OpenCode runner")
            yield reasoning_step(
                event_type="ERROR",
                message="Unexpected error",
                details={"error": str(e)[:500]},
            ).model_dump()
        finally:
            session_manager.set_current_process(None)
            session_manager.release_process_lock()

    def check_availability(self) -> tuple[bool, str]:
        """Check if OpenCode is available."""
        return check_opencode_installed()

    async def list_models(self) -> List[ModelInfo]:
        """List enabled models via OpenCode server's v2 /api/model endpoint.

        Starts a temporary OpenCode server if none is running, queries
        the /api/model endpoint to discover all configured models, and
        returns a list of only enabled models.
        """
        binary = find_opencode_binary()
        if not binary:
            logger.warning("OpenCode binary not found, cannot list models")
            return []

        port = settings.opencode_default_port
        base_url = f"http://127.0.0.1:{port}"

        server_already_running = False
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{base_url}/global/health")
                server_already_running = resp.status_code == 200
        except Exception:
            server_already_running = False

        server_process = None
        if not server_already_running:
            logger.info(f"Starting temporary OpenCode server on port {port}")
            server_process = await asyncio.create_subprocess_exec(
                binary,
                "serve",
                "--port",
                str(port),
                "--hostname",
                "127.0.0.1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            for _ in range(20):
                await asyncio.sleep(0.5)
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.get(f"{base_url}/global/health")
                        if resp.status_code == 200:
                            break
                except Exception:
                    pass
                if server_process.returncode is not None:
                    logger.warning("OpenCode server exited prematurely")
                    stderr = ""
                    if server_process.stderr:
                        stderr = (await server_process.stderr.read()).decode()
                    logger.warning(f"Server stderr: {stderr[:500]}")
                    return []

        models: List[ModelInfo] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                enabled_provider_ids: set = set()
                provider_resp = await client.get(f"{base_url}/api/provider")
                if provider_resp.status_code == 200:
                    providers = provider_resp.json()
                    if isinstance(providers, list):
                        for p in providers:
                            p_enabled = p.get("enabled")
                            if p_enabled is False:
                                continue
                            enabled_provider_ids.add(p.get("id", ""))
                else:
                    logger.warning(
                        f"Failed to fetch providers: HTTP {provider_resp.status_code}"
                    )

                if not enabled_provider_ids:
                    logger.warning("No enabled providers found")
                    return []

                resp = await client.get(f"{base_url}/api/model")
                if resp.status_code != 200:
                    logger.warning(f"Failed to fetch models: HTTP {resp.status_code}")
                    return []

                data = resp.json()
                if isinstance(data, list):
                    for model in data:
                        model_id = model.get("id", "")
                        provider_id = model.get("providerID", "")
                        if provider_id not in enabled_provider_ids:
                            continue
                        if model.get("enabled") is not True:
                            continue
                        model_name = model.get("name", model_id)
                        models.append(
                            ModelInfo(
                                id=model_id,
                                name=model_name,
                                provider=provider_id,
                            )
                        )
        except Exception as e:
            logger.exception(f"Failed to fetch models from OpenCode server: {e}")
        finally:
            if server_process is not None and not server_already_running:
                server_process.terminate()
                try:
                    await asyncio.wait_for(server_process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    server_process.kill()
                    await server_process.wait()

        return models


def get_code_generator(generator_type: str) -> CodeGenerator:
    """Get code generator instance based on type."""
    if generator_type == "claude":
        return ClaudeCodeGenerator()
    elif generator_type == "opencode":
        return OpenCodeGenerator()
    else:
        raise ValueError(f"Unknown code generator type: {generator_type}")
