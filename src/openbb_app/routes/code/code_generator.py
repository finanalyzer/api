"""Code generator abstract base class and implementations."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Optional

from .session_manager import Session


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
    ) -> AsyncGenerator[Dict, None]:
        """Run code generation with the given prompt."""
        pass

    @abstractmethod
    def check_availability(self) -> tuple[bool, str]:
        """Check if the code generator is available."""
        pass


class ClaudeCodeGenerator(CodeGenerator):
    """Claude Code CLI generator implementation."""

    async def run(
        self, prompt: str, session: Session, config: CodeGeneratorConfig
    ) -> AsyncGenerator[Dict, None]:
        """Run Claude Code CLI."""
        from .claude_runner import run_claude_code, ClaudeRunnerConfig

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


class OpenCodeGenerator(CodeGenerator):
    """OpenCode generator implementation."""

    def find_opencode_binary(self) -> Optional[str]:
        """Find the OpenCode binary.

        Returns:
            Path to opencode binary if found, None otherwise.
        """
        import shutil
        import os

        # Check if opencode is in PATH
        opencode_path = shutil.which("opencode")
        if opencode_path:
            return opencode_path

        # Check common installation locations
        common_paths = [
            os.path.expanduser("~/.opencode/bin/opencode"),
            "/usr/local/bin/opencode",
            "/opt/homebrew/bin/opencode",
        ]

        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        return None

    async def run(
        self, prompt: str, session: Session, config: CodeGeneratorConfig
    ) -> AsyncGenerator[Dict, None]:
        """Run OpenCode."""
        import asyncio
        import json
        import logging
        import os

        from openbb_ai import message_chunk, reasoning_step
        from .output_parser import ParsedEvent
        from .session_manager import session_manager

        logger = logging.getLogger(__name__)

        opencode_binary = self.find_opencode_binary()
        if not opencode_binary:
            yield reasoning_step(
                event_type="ERROR",
                message="OpenCode binary not found",
                details={"error": "Please install OpenCode and add it to your PATH"},
            ).model_dump()
            yield message_chunk("OpenCode is not installed. Please install it and try again.").model_dump()
            return

        # Determine working directory
        cwd = config.working_directory
        if not cwd:
            cwd = os.getcwd()

        # Build command
        cmd = [
            opencode_binary,
            "run",
            prompt,
        ]

        logger.info(f"Starting OpenCode: cwd={cwd}, session={session.session_id}")
        logger.debug(f"Command: {' '.join(cmd[:5])}...")

        yield reasoning_step(
            event_type="INFO",
            message="Starting OpenCode execution",
            details={
                "session_id": session.session_id,
                "working_dir": cwd,
            },
        ).model_dump()

        try:
            await session_manager.acquire_process_lock()

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                limit=10 * 1024 * 1024,  # 10MB buffer limit
            )

            session_manager.set_current_process(process, session.session_id)

            stderr_lines: list[str] = []

            async def read_stderr():
                if process.stderr:
                    async for line in process.stderr:
                        if line:
                            stderr_lines.append(line.decode("utf-8"))

            stderr_task = asyncio.create_task(read_stderr())

            logger.info(f"OpenCode process started with PID {process.pid}")

            if process.stdout:
                line_count = 0
                async for line in process.stdout:
                    if not line:
                        continue

                    line_count += 1
                    try:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue

                        # Log every 10th line to track progress
                        if line_count % 10 == 0:
                            logger.debug(f"Processed {line_count} lines from OpenCode")

                        # Try to parse as JSON
                        try:
                            event = json.loads(line_str)
                            # Process OpenCode event
                            if "content" in event:
                                yield message_chunk(event["content"]).model_dump()
                            else:
                                # Fallback to message chunk
                                yield message_chunk(line_str).model_dump()
                        except json.JSONDecodeError:
                            # Non-JSON line, treat as message chunk
                            yield message_chunk(line_str).model_dump()

                    except Exception as e:
                        logger.error(f"Parse error on line {line_count}: {e}")
                        yield reasoning_step(
                            event_type="WARNING",
                            message="Parse error",
                            details={"error": str(e)[:200]},
                        ).model_dump()

                logger.info(f"OpenCode output complete: {line_count} lines processed")

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
                yield message_chunk(f"\n\n**Execution timed out after {config.timeout} seconds.**").model_dump()

            await stderr_task

            if stderr_lines:
                stderr_text = "".join(stderr_lines)
                logger.warning(f"OpenCode stderr: {stderr_text[:500]}")

                yield reasoning_step(
                    event_type="ERROR" if process.returncode != 0 else "WARNING",
                    message="OpenCode stderr output",
                    details={"stderr": stderr_text[:1000]},
                ).model_dump()
                yield message_chunk(f"\n\n**{'Error' if process.returncode != 0 else 'Warning'}:**\n```\n{stderr_text[:2000]}\n```\n").model_dump()

            yield reasoning_step(
                event_type="INFO" if process.returncode == 0 else "ERROR",
                message=f"OpenCode {'completed' if process.returncode == 0 else 'failed'}",
                details={"exit_code": process.returncode},
            ).model_dump()

            if process.returncode != 0:
                yield message_chunk(f"\n\n**OpenCode exited with code {process.returncode}.**\n").model_dump()

        except FileNotFoundError:
            yield reasoning_step(
                event_type="ERROR",
                message="OpenCode binary not found",
                details={"path": opencode_binary},
            ).model_dump()
        except PermissionError:
            yield reasoning_step(
                event_type="ERROR",
                message="Permission denied",
                details={"path": opencode_binary},
            ).model_dump()
        except Exception as e:
            logger.exception("Unexpected error in OpenCode runner")
            yield reasoning_step(
                event_type="ERROR",
                message="Unexpected error",
                details={"error": str(e)[:500]},
            ).model_dump()
            # Also emit a user-friendly message
            yield message_chunk(f"\n\n**Error:** An unexpected error occurred: {str(e)[:200]}\n\n"
            "This may be due to a tool or MCP server not being available. "
            "Please try again or check the server logs.").model_dump()
        finally:
            session_manager.set_current_process(None)
            session_manager.release_process_lock()

    def check_availability(self) -> tuple[bool, str]:
        """Check if OpenCode is available."""
        binary = self.find_opencode_binary()
        if binary:
            return True, f"OpenCode found at: {binary}"
        return False, "OpenCode not found. Please install it and add to PATH"


def get_code_generator(generator_type: str) -> CodeGenerator:
    """Get code generator instance based on type."""
    if generator_type == "claude":
        return ClaudeCodeGenerator()
    elif generator_type == "opencode":
        return OpenCodeGenerator()
    else:
        raise ValueError(f"Unknown code generator type: {generator_type}")
