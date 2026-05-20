"""Claude Code CLI subprocess runner.

Manages spawning and communication with Claude Code CLI for app building.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

from openbb_ai import message_chunk, reasoning_step

from .config import find_claude_binary, settings
from .output_parser import ParsedEvent, parse_claude_event
from .session_manager import Session, session_manager

logger = logging.getLogger(__name__)


@dataclass
class ClaudeRunnerConfig:
    """Configuration for Claude Code CLI invocation."""

    working_directory: Optional[str] = None
    timeout: float = 600.0
    skip_permissions: bool = True
    verbose: bool = True


async def run_claude_code(
    prompt: str,
    session: Session,
    config: Optional[ClaudeRunnerConfig] = None,
) -> AsyncGenerator[ParsedEvent, None]:
    """Run Claude Code CLI and stream parsed events.

    Args:
        prompt: The full prompt to send to Claude.
        session: Session object for context management.
        config: Optional configuration overrides.

    Yields:
        ParsedEvent objects for SSE streaming.
    """
    config = config or ClaudeRunnerConfig()

    claude_binary = find_claude_binary()
    if not claude_binary:
        yield ParsedEvent(
            event_type="reasoning_step",
            data=reasoning_step(
                event_type="ERROR",
                message="Claude Code CLI not found",
                details={
                    "error": "Please install from https://docs.anthropic.com/en/docs/claude-code"
                },
            ).model_dump(),
        )
        return

    # Determine working directory
    cwd = config.working_directory
    if not cwd and settings.resolved_target_repo:
        cwd = str(settings.resolved_target_repo)
    if not cwd:
        cwd = os.getcwd()

    # Build command - verbose is required for stream-json with --print
    cmd = [
        claude_binary,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--chrome",  # Enable Chrome browser integration MCP
    ]

    if config.skip_permissions:
        cmd.append("--dangerously-skip-permissions")

    if session.is_continued:
        # Continue existing session - use --continue with --resume
        cmd.extend(["--resume", session.session_id])
    else:
        # New session - just set the session ID
        cmd.extend(["--session-id", session.session_id])

    cmd.append(prompt)

    logger.info(f"Starting Claude Code: cwd={cwd}, session={session.session_id}")
    logger.debug(f"Command: {' '.join(cmd[:5])}...")  # Log first 5 args

    yield ParsedEvent(
        event_type="reasoning_step",
        data=reasoning_step(
            event_type="INFO",
            message="Starting Claude Code execution",
            details={
                "session_id": session.session_id,
                "working_dir": cwd,
                "continued": session.is_continued,
            },
        ).model_dump(),
    )

    try:
        await session_manager.acquire_process_lock()

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            limit=10 * 1024 * 1024,  # 10MB buffer limit for large outputs (screenshots)
        )

        session_manager.set_current_process(process, session.session_id)

        stderr_lines: list[str] = []

        async def read_stderr():
            if process.stderr:
                async for line in process.stderr:
                    if line:
                        stderr_lines.append(line.decode("utf-8"))

        stderr_task = asyncio.create_task(read_stderr())

        logger.info(f"Claude Code process started with PID {process.pid}")

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
                        logger.debug(f"Processed {line_count} lines from Claude Code")

                    event = json.loads(line_str)

                    for parsed_event in parse_claude_event(event):
                        yield parsed_event

                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON line: {line[:100]}...")
                    yield ParsedEvent(
                        event_type="message_chunk",
                        data=message_chunk(line.decode("utf-8")).model_dump(),
                    )
                except Exception as e:
                    logger.error(f"Parse error on line {line_count}: {e}")
                    yield ParsedEvent(
                        event_type="reasoning_step",
                        data=reasoning_step(
                            event_type="WARNING",
                            message="Parse error",
                            details={"error": str(e)[:200]},
                        ).model_dump(),
                    )

            logger.info(f"Claude Code output complete: {line_count} lines processed")

        try:
            await asyncio.wait_for(process.wait(), timeout=config.timeout)
        except asyncio.TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

            yield ParsedEvent(
                event_type="reasoning_step",
                data=reasoning_step(
                    event_type="ERROR",
                    message="Execution timed out",
                    details={"timeout_seconds": config.timeout},
                ).model_dump(),
            )
            yield ParsedEvent(
                event_type="message_chunk",
                data=message_chunk(
                    f"\n\n**Execution timed out after {config.timeout} seconds.**"
                ).model_dump(),
            )

        await stderr_task

        if stderr_lines:
            stderr_text = "".join(stderr_lines)
            logger.warning(f"Claude stderr: {stderr_text[:500]}")

            yield ParsedEvent(
                event_type="reasoning_step",
                data=reasoning_step(
                    event_type="ERROR" if process.returncode != 0 else "WARNING",
                    message="Claude Code stderr output",
                    details={"stderr": stderr_text[:1000]},
                ).model_dump(),
            )
            yield ParsedEvent(
                event_type="message_chunk",
                data=message_chunk(
                    f"\n\n**{'Error' if process.returncode != 0 else 'Warning'}:**\n```\n{stderr_text[:2000]}\n```\n"
                ).model_dump(),
            )

        yield ParsedEvent(
            event_type="reasoning_step",
            data=reasoning_step(
                event_type="INFO" if process.returncode == 0 else "ERROR",
                message=f"Claude Code {'completed' if process.returncode == 0 else 'failed'}",
                details={"exit_code": process.returncode},
            ).model_dump(),
        )

        if process.returncode != 0:
            yield ParsedEvent(
                event_type="message_chunk",
                data=message_chunk(
                    f"\n\n**Claude exited with code {process.returncode}.**\n"
                ).model_dump(),
            )

    except FileNotFoundError:
        yield ParsedEvent(
            event_type="reasoning_step",
            data=reasoning_step(
                event_type="ERROR",
                message="Claude Code binary not found",
                details={"path": claude_binary},
            ).model_dump(),
        )
    except PermissionError:
        yield ParsedEvent(
            event_type="reasoning_step",
            data=reasoning_step(
                event_type="ERROR",
                message="Permission denied",
                details={"path": claude_binary},
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Unexpected error in Claude runner")
        yield ParsedEvent(
            event_type="reasoning_step",
            data=reasoning_step(
                event_type="ERROR",
                message="Unexpected error",
                details={"error": str(e)[:500]},
            ).model_dump(),
        )
        # Also emit a user-friendly message
        yield ParsedEvent(
            event_type="message_chunk",
            data=message_chunk(
                f"\n\n**Error:** An unexpected error occurred: {str(e)[:200]}\n\n"
                "This may be due to a tool or MCP server not being available. "
                "Please try again or check the server logs."
            ).model_dump(),
        )
    finally:
        session_manager.set_current_process(None)
        session_manager.release_process_lock()
