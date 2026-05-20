"""Parser for Claude Code CLI JSON stream output.

Claude Code CLI with --output-format stream-json outputs one JSON object per line.
This module parses these events and converts them to OpenBB Copilot SSE events.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Generator

from openbb_ai import message_chunk, reasoning_step

logger = logging.getLogger(__name__)


def format_tool_message(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Generate a human-readable message describing a tool execution.

    Args:
        tool_name: The name of the tool being executed.
        tool_input: The input parameters for the tool.

    Returns:
        A descriptive message about what the tool is doing.
    """
    name_lower = tool_name.lower()

    # File reading tools
    if name_lower == "read":
        file_path = tool_input.get("file_path", "")
        if file_path:
            # Extract just the filename or last part of path
            short_path = file_path.split("/")[-1] if "/" in file_path else file_path
            return f"Reading file: {short_path}"
        return "Reading file"

    # File writing tools
    if name_lower == "write":
        file_path = tool_input.get("file_path", "")
        if file_path:
            short_path = file_path.split("/")[-1] if "/" in file_path else file_path
            return f"Creating file: {short_path}"
        return "Creating file"

    # File editing tools
    if name_lower == "edit":
        file_path = tool_input.get("file_path", "")
        if file_path:
            short_path = file_path.split("/")[-1] if "/" in file_path else file_path
            return f"Editing file: {short_path}"
        return "Editing file"

    # Shell/bash commands
    if name_lower == "bash":
        command = tool_input.get("command", "")
        description = tool_input.get("description", "")
        if description:
            return f"Running: {description}"
        if command:
            # Truncate long commands
            short_cmd = command[:50] + "..." if len(command) > 50 else command
            return f"Running: {short_cmd}"
        return "Running shell command"

    # File search tools
    if name_lower == "glob":
        pattern = tool_input.get("pattern", "")
        if pattern:
            return f"Searching for files: {pattern}"
        return "Searching for files"

    # Content search tools
    if name_lower == "grep":
        pattern = tool_input.get("pattern", "")
        if pattern:
            short_pattern = pattern[:30] + "..." if len(pattern) > 30 else pattern
            return f"Searching for: '{short_pattern}'"
        return "Searching file contents"

    # Task/agent tools
    if name_lower == "task":
        description = tool_input.get("description", "")
        if description:
            return f"Spawning agent: {description}"
        return "Spawning sub-agent"

    # Chrome MCP tools (browser automation)
    if name_lower.startswith("mcp__claude-in-chrome__"):
        action_name = name_lower.replace("mcp__claude-in-chrome__", "")

        if action_name == "computer":
            action = tool_input.get("action", "")
            if action == "screenshot":
                return "Taking screenshot"
            elif action == "left_click":
                return "Clicking element"
            elif action == "type":
                text = tool_input.get("text", "")
                short_text = text[:30] + "..." if len(text) > 30 else text
                return f"Typing: {short_text}"
            elif action == "scroll":
                direction = tool_input.get("scroll_direction", "")
                return f"Scrolling {direction}"
            return f"Browser action: {action}"

        if action_name == "navigate":
            url = tool_input.get("url", "")
            short_url = url[:50] + "..." if len(url) > 50 else url
            return f"Navigating to: {short_url}"

        if action_name == "read_page":
            return "Reading page content"

        if action_name == "find":
            query = tool_input.get("query", "")
            return f"Finding element: {query}"

        if action_name == "form_input":
            return "Filling form field"

        if action_name == "tabs_context_mcp":
            return "Getting browser tabs"

        if action_name == "tabs_create_mcp":
            return "Creating new browser tab"

        if action_name == "get_page_text":
            return "Extracting page text"

        return f"Browser: {action_name}"

    # Todo tools
    if name_lower == "todowrite":
        todos = tool_input.get("todos", [])
        if todos:
            return f"Updating task list ({len(todos)} items)"
        return "Updating task list"

    # List directory
    if name_lower == "ls":
        path = tool_input.get("path", "")
        if path:
            return f"Listing directory: {path}"
        return "Listing directory"

    # Default fallback
    return f"Executing: {tool_name}"


@dataclass
class ParsedEvent:
    """A parsed event ready to be yielded as SSE."""

    event_type: str
    data: dict[str, Any]


def parse_claude_event(event: dict[str, Any]) -> Generator[ParsedEvent, None, None]:
    """Parse a single Claude Code JSON event into OpenBB SSE events.

    Args:
        event: A parsed JSON object from Claude Code's stream output.

    Yields:
        ParsedEvent objects to be converted to SSE.
    """
    event_type = event.get("type", "")

    if event_type == "system":
        subtype = event.get("subtype", "")
        if subtype == "init":
            yield ParsedEvent(
                event_type="reasoning_step",
                data=reasoning_step(
                    event_type="INFO",
                    message="Claude Code session initialized",
                    details={"session_id": event.get("session_id", "")},
                ).model_dump(),
            )

    elif event_type == "stream_event":
        # Real-time streaming events from Claude
        inner_event = event.get("event", {})
        inner_type = inner_event.get("type", "")

        if inner_type == "content_block_delta":
            delta = inner_event.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                text = delta.get("text", "")
                if text:
                    yield ParsedEvent(
                        event_type="message_chunk",
                        data=message_chunk(text).model_dump(),
                    )

    elif event_type == "assistant":
        # Complete assistant message (may contain tool_use and text)
        message = event.get("message", {})
        content = message.get("content", [])

        for block in content:
            block_type = block.get("type", "")

            if block_type == "tool_use":
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})

                # Generate descriptive message
                message = format_tool_message(tool_name, tool_input)

                details = {"tool": tool_name}
                if tool_input:
                    input_str = json.dumps(tool_input)
                    if len(input_str) > 300:
                        input_str = input_str[:300] + "..."
                    details["input"] = input_str

                yield ParsedEvent(
                    event_type="reasoning_step",
                    data=reasoning_step(
                        event_type="INFO",
                        message=message,
                        details=details,
                    ).model_dump(),
                )

            elif block_type == "text":
                # Text content from assistant
                text = block.get("text", "")
                if text:
                    yield ParsedEvent(
                        event_type="message_chunk",
                        data=message_chunk(text).model_dump(),
                    )

    elif event_type == "user":
        # Tool result being fed back to Claude
        content = event.get("content", [])

        for block in content:
            block_type = block.get("type", "")

            if block_type == "tool_result":
                tool_content = block.get("content", "")
                is_error = block.get("is_error", False)

                if isinstance(tool_content, str) and len(tool_content) > 500:
                    display_content = tool_content[:500] + "..."
                else:
                    display_content = str(tool_content)[:500]

                yield ParsedEvent(
                    event_type="reasoning_step",
                    data=reasoning_step(
                        event_type="ERROR" if is_error else "INFO",
                        message="Tool failed" if is_error else "Tool completed",
                        details={"output": display_content},
                    ).model_dump(),
                )

    elif event_type == "result":
        # Final result from Claude Code
        result_text = event.get("result", "")
        is_error = event.get("is_error", False)

        logger.info(
            f"Received result event: is_error={is_error}, "
            f"result_length={len(result_text) if result_text else 0}"
        )
        if result_text:
            logger.debug(f"Result text preview: {result_text[:200]}...")

        if is_error:
            yield ParsedEvent(
                event_type="reasoning_step",
                data=reasoning_step(
                    event_type="ERROR",
                    message="Execution failed",
                    details={
                        "error": result_text[:500] if result_text else "Unknown error"
                    },
                ).model_dump(),
            )
            if result_text:
                yield ParsedEvent(
                    event_type="message_chunk",
                    data=message_chunk(f"\n\n**Error:**\n{result_text}").model_dump(),
                )
        else:
            # Always emit completion message
            yield ParsedEvent(
                event_type="reasoning_step",
                data=reasoning_step(
                    event_type="INFO",
                    message="Claude Code completed successfully",
                    details={"result_length": len(result_text) if result_text else 0},
                ).model_dump(),
            )
            if result_text:
                # Emit final result text as message chunk
                logger.info(f"Emitting final result text ({len(result_text)} chars)")
                yield ParsedEvent(
                    event_type="message_chunk",
                    data=message_chunk(result_text).model_dump(),
                )
            else:
                # No result text - emit a generic completion message
                logger.warning("No result text received from Claude Code")
                yield ParsedEvent(
                    event_type="message_chunk",
                    data=message_chunk(
                        "\n\n✅ **Task completed.** Check the workspace to see the results."
                    ).model_dump(),
                )
