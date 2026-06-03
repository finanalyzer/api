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
        """Run OpenCode via HTTP API with fallback to CLI."""
        opencode_config = OpenCodeRunnerConfig(
            working_directory=config.working_directory,
            timeout=config.timeout,
            port=settings.opencode_default_port,
            model_id=settings.default_model,
        )

        server_ok, server_result = await ensure_opencode_server(opencode_config)
        if not server_ok:
            logger.warning(f"OpenCode server not available: {server_result}")
            # Fallback to CLI if server is not available
            async for item in self._run_via_cli(prompt, session, config):
                yield item
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
            logger.info("Acquiring process lock...")
            await session_manager.acquire_process_lock()
            logger.info("Process lock acquired, creating HTTP client...")

            async with httpx.AsyncClient(timeout=config.timeout) as client:
                logger.info("HTTP client created, creating session...")

                async def _create_new_session() -> Optional[str]:
                    """Create a fresh OpenCode session, returning its ID or None on failure."""
                    # The OpenCode API expects just the model name without the provider prefix
                    # e.g., "deepseek-v4-flash-free" not "opencode/deepseek-v4-flash-free"
                    api_model_id = settings.default_model.split("/")[-1]
                    logger.info(f"Creating session with model: {settings.default_model} (API: {api_model_id})")
                    create_resp = await client.post(
                        f"{base_url}/session", json={"modelID": api_model_id}
                    )
                    logger.info(f"Session creation response: {create_resp.status_code}")
                    if create_resp.status_code != 200:
                        logger.warning(f"Failed to create session: {create_resp.text[:200]}")
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
                    logger.info("Creating new OpenCode session...")
                    opencode_session_id = await _create_new_session()
                    if not opencode_session_id:
                        logger.warning("Failed to create OpenCode session via API, trying CLI")
                        session_manager.set_current_process(None)
                        session_manager.release_process_lock()
                        async for item in self._run_via_cli(prompt, session, config):
                            yield item
                        return
                    session.opencode_session_id = opencode_session_id
                    logger.info(f"Created OpenCode session: {opencode_session_id}")

                yield reasoning_step(
                    event_type="INFO",
                    message="Sending message to OpenCode...",
                    details={},
                ).model_dump()

                # Send message to OpenCode
                message_resp = await client.post(
                    f"{base_url}/session/{opencode_session_id}/message",
                    json={
                        "parts": [{"type": "text", "text": prompt}],
                    },
                )
                
                if message_resp.status_code != 200:
                    logger.warning(f"Failed to send message via API, trying CLI")
                    session_manager.set_current_process(None)
                    session_manager.release_process_lock()
                    async for item in self._run_via_cli(prompt, session, config):
                        yield item
                    return

                # Handle potential empty or non-JSON response
                try:
                    message_data = message_resp.json()
                except json.JSONDecodeError as e:
                    response_content = message_resp.content.decode('utf-8') if message_resp.content else 'empty'
                    logger.warning(f"API returned non-JSON response, trying CLI: {response_content[:200]}")
                    session_manager.set_current_process(None)
                    session_manager.release_process_lock()
                    async for item in self._run_via_cli(prompt, session, config):
                        yield item
                    return

                # Check for error responses
                error_info = message_data.get("error") or message_data.get("info", {}).get("error")
                if error_info:
                    error_message = error_info.get("message") or \
                                  error_info.get("data", {}).get("message") or \
                                  str(error_info)
                    logger.warning(f"API error, trying CLI: {error_message}")
                    session_manager.set_current_process(None)
                    session_manager.release_process_lock()
                    async for item in self._run_via_cli(prompt, session, config):
                        yield item
                    return

                # Extract parts from response
                parts = message_data.get("parts", [])
                
                # If no parts found, check alternative response structures
                if not parts:
                    info_data = message_data.get("info", {})
                    parts = info_data.get("parts", [])
                
                # If still no parts found, check more alternative structures
                if not parts:
                    if "text" in message_data:
                        parts = [{"type": "text", "text": message_data["text"]}]
                    elif "content" in message_data:
                        parts = [{"type": "text", "text": str(message_data["content"])}]
                    elif "response" in message_data:
                        response = message_data["response"]
                        if isinstance(response, str):
                            parts = [{"type": "text", "text": response}]
                        elif isinstance(response, dict) and "text" in response:
                            parts = [{"type": "text", "text": response["text"]}]
                    elif "text" in info_data:
                        parts = [{"type": "text", "text": info_data["text"]}]

                logger.info(f"Received response with {len(parts)} parts")

                # If still no parts found, fallback to CLI
                if not parts:
                    logger.warning("API returned no content, trying CLI")
                    session_manager.set_current_process(None)
                    session_manager.release_process_lock()
                    async for item in self._run_via_cli(prompt, session, config):
                        yield item
                    return

                # Process response parts
                for part in parts:
                    part_type = part.get("type")
                    if part_type == "text":
                        yield message_chunk(part.get("text", "")).model_dump()
                    elif part_type == "tool_result":
                        yield reasoning_step(
                            event_type="INFO",
                            message="Tool execution result",
                            details={"tool_result": part},
                        ).model_dump()

                yield reasoning_step(
                    event_type="INFO",
                    message="OpenCode completed successfully",
                    details={},
                ).model_dump()

        except httpx.TimeoutException:
            logger.warning("API timeout, trying CLI")
            session_manager.set_current_process(None)
            session_manager.release_process_lock()
            async for item in self._run_via_cli(prompt, session, config):
                yield item
            return
        except Exception as e:
            logger.warning(f"API error: {e}, trying CLI")
            session_manager.set_current_process(None)
            session_manager.release_process_lock()
            async for item in self._run_via_cli(prompt, session, config):
                yield item
            return
        finally:
            session_manager.set_current_process(None)
            session_manager.release_process_lock()

    async def _run_via_cli(
        self, prompt: str, session: Session, config: CodeGeneratorConfig
    ) -> AsyncGenerator[dict, None]:
        """Run OpenCode via CLI as fallback."""
        opencode_binary = find_opencode_binary()
        if not opencode_binary:
            yield reasoning_step(
                event_type="ERROR",
                message="OpenCode CLI not found",
                details={
                    "error": "Please install OpenCode from https://opencode.ai"
                },
            ).model_dump()
            return

        # Determine working directory
        cwd = config.working_directory
        if not cwd and settings.resolved_target_repo:
            cwd = str(settings.resolved_target_repo)
        if not cwd:
            cwd = os.getcwd()

        model_id = settings.default_model or "opencode/deepseek-v4-flash-free"

        try:
            await session_manager.acquire_process_lock()

            # Build command
            cmd = [
                opencode_binary,
                "run",
                prompt,
                "--model",
                model_id,
                "--format",
                "json",
            ]

            logger.info(f"Starting OpenCode CLI: cwd={cwd}, model={model_id}")
            logger.info(f"CLI command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Merge stderr into stdout
                stdin=asyncio.subprocess.DEVNULL,  # Use DEVNULL to prevent blocking
                cwd=cwd,
                limit=10 * 1024 * 1024,
            )

            logger.info(f"CLI process started with PID: {process.pid}")
            session_manager.set_current_process(process, session.session_id)

            stdout_received = False

            # Read stdout line by line (JSON format)
            if process.stdout:
                async for line in process.stdout:
                    if not line:
                        continue

                    try:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue
                        
                        # Parse JSON event
                        event = json.loads(line_str)
                        event_type = event.get("type", "")
                        
                        # Extract text content from text events
                        if event_type == "text":
                            text = event.get("part", {}).get("text", "")
                            if text:
                                stdout_received = True
                                yield message_chunk(text).model_dump()
                        elif event_type == "thought":
                            thought = event.get("part", {}).get("thought", "")
                            if thought:
                                yield reasoning_step(
                                    event_type="THOUGHT",
                                    message=thought,
                                ).model_dump()

                    except json.JSONDecodeError:
                        # Fallback for non-JSON output
                        stdout_received = True
                        yield message_chunk(line_str).model_dump()
                    except Exception as e:
                        logger.error(f"Error processing CLI output: {e}")

            # Wait for process to complete with timeout
            try:
                await asyncio.wait_for(process.wait(), timeout=config.timeout)
            except asyncio.TimeoutError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                yield reasoning_step(
                    event_type="ERROR",
                    message="Execution timed out",
                    details={"timeout_seconds": config.timeout},
                ).model_dump()
                yield message_chunk(
                    f"\n\n**Execution timed out after {config.timeout} seconds.**\n\n"
                    "This may indicate that OpenCode is not available in this environment.\n"
                    "Please check that OpenCode is installed and the model is accessible."
                ).model_dump()
                session_manager.set_current_process(None)
                session_manager.release_process_lock()
                return

            # If no output was received, show error
            if not stdout_received and process.returncode == 0:
                yield reasoning_step(
                    event_type="ERROR",
                    message="No response content",
                    details={},
                ).model_dump()
                yield message_chunk(
                    "\n\n**Error:** No response was received from OpenCode.\n\n"
                    "This may be due to model availability issues or network problems.\n"
                    "Please try again later."
                ).model_dump()

            yield reasoning_step(
                event_type="INFO" if process.returncode == 0 else "ERROR",
                message=f"OpenCode CLI {'completed' if process.returncode == 0 else 'failed'}",
                details={"exit_code": process.returncode},
            ).model_dump()

        except FileNotFoundError:
            yield reasoning_step(
                event_type="ERROR",
                message="OpenCode CLI not found",
                details={"error": "OpenCode CLI is not installed or not in PATH"},
            ).model_dump()
            yield message_chunk(
                "\n\n**Error:** OpenCode CLI is not available.\n\n"
                "Please install OpenCode from https://opencode.ai\n"
                "or configure the OpenCode server endpoint."
            ).model_dump()
        except PermissionError:
            yield reasoning_step(
                event_type="ERROR",
                message="Permission denied",
                details={"error": "Cannot execute OpenCode CLI"},
            ).model_dump()
            yield message_chunk(
                "\n\n**Error:** Permission denied when trying to run OpenCode.\n\n"
                "Please check file permissions for the OpenCode binary."
            ).model_dump()
        except Exception as e:
            logger.exception("Unexpected error in OpenCode CLI runner")
            yield reasoning_step(
                event_type="ERROR",
                message="Unexpected error",
                details={"error": str(e)[:500]},
            ).model_dump()
            yield message_chunk(
                f"\n\n**Error:** An unexpected error occurred: {str(e)[:200]}\n\n"
                "Please try again or check the server logs."
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
