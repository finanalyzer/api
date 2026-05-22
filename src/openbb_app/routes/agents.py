"""OpenBB App Builder Agent.

A FastAPI server that bridges OpenBB Copilot with code generators,
enabling local app generation using .claude skills and reference backends.
"""

import argparse
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi import APIRouter, HTTPException
from fastapi import Path as FastAPIPath
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openbb_ai import message_chunk, reasoning_step
from openbb_ai.models import QueryRequest
from sse_starlette.sse import EventSourceResponse

from .code.code_generator import CodeGeneratorConfig, get_code_generator
from .code.config import check_target_repo, settings
from .code.prompt_builder import build_continuation_prompt, build_prompt
from .code.request_parser import extract_conversation_id, parse_request
from .code.session_manager import session_manager


logger = logging.getLogger(__name__)

# 创建路由器
agent_router = APIRouter()


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - check dependencies on startup."""
    # Check code generator availability
    try:
        generator = get_code_generator(settings.code_generator)
        gen_ok, gen_msg = generator.check_availability()
        if not gen_ok:
            logger.warning(f"{settings.code_generator} generator: {gen_msg}")
        else:
            logger.info(f"{settings.code_generator} generator: {gen_msg}")
    except ValueError as e:
        logger.error(f"Invalid code generator: {e}")

    repo_ok, repo_msg = check_target_repo()
    if not repo_ok:
        logger.warning(f"Target repo: {repo_msg}")
    else:
        logger.info(f"Target repo: {repo_msg}")

    yield

@agent_router.get("/health")
def health() -> JSONResponse:
    """Health check with dependency status."""
    # Check code generator availability
    gen_ok = False
    gen_msg = ""
    try:
        generator = get_code_generator(settings.code_generator)
        gen_ok, gen_msg = generator.check_availability()
    except ValueError as e:
        gen_msg = str(e)

    repo_ok, repo_msg = check_target_repo()

    # Determine overall status
    if gen_ok and repo_ok:
        status = "healthy"
    elif gen_ok:
        status = "degraded"  # Can run but no target repo
    else:
        status = "unhealthy"

    return JSONResponse(
        content={
            "status": status,
            "service": "openbb-app-builder-agent",
            "dependencies": {
                "code_generator": {
                    "type": settings.code_generator,
                    "available": gen_ok,
                    "message": gen_msg
                },
                "target_repo": {"available": repo_ok, "message": repo_msg},
            },
        }
    )



@agent_router.post("/query")
async def query(request: QueryRequest) -> EventSourceResponse:
    """Process a query from OpenBB Copilot.

    Receives the user's query, extracts widget/tool context,
    and streams responses back as SSE events.
    """
    # Check code generator availability
    try:
        generator = get_code_generator(settings.code_generator)
        gen_ok, gen_msg = generator.check_availability()
        if not gen_ok:

            async def error_response() -> AsyncGenerator[dict, None]:
                yield reasoning_step(
                    event_type="ERROR",
                    message=f"{settings.code_generator} not available",
                    details={"error": gen_msg},
                ).model_dump()
                yield message_chunk(
                    f"{settings.code_generator} is not available: {gen_msg}"
                ).model_dump()

            return EventSourceResponse(
                content=error_response(),
                media_type="text/event-stream",
            )
    except ValueError as e:
        async def error_response() -> AsyncGenerator[dict, None]:
            yield reasoning_step(
                event_type="ERROR",
                message="Invalid code generator",
                details={"error": str(e)},
            ).model_dump()
            yield message_chunk(
                f"Invalid code generator: {str(e)}"
            ).model_dump()

        return EventSourceResponse(
            content=error_response(),
            media_type="text/event-stream",
        )

    # Parse request into normalized context
    context = parse_request(request)

    # Check if we should execute (last message must be human)
    if not context.should_execute:

        async def skip_response() -> AsyncGenerator[dict, None]:
            yield message_chunk("Waiting for user input...").model_dump()

        return EventSourceResponse(
            content=skip_response(),
            media_type="text/event-stream",
        )

    # No user message
    if not context.user_message:

        async def empty_response() -> AsyncGenerator[dict, None]:
            yield message_chunk("No message provided.").model_dump()

        return EventSourceResponse(
            content=empty_response(),
            media_type="text/event-stream",
        )

    # Get or create session
    conversation_id = extract_conversation_id(request)
    session = session_manager.get_or_create_session(conversation_id)

    # Persist context for debugging/reproducibility
    session_manager.persist_context(session, context.to_dict())

    logger.info(
        f"Processing query: session={session.session_id}, "
        f"continued={session.is_continued}, "
        f"widgets={len(context.primary_widgets)}, "
        f"tool_results={len(context.tool_results)}"
    )
    logger.info(f"User message: {context.user_message[:100]}...")
    if settings.resolved_target_repo:
        logger.info(f"Target repo: {settings.resolved_target_repo}")
    else:
        logger.warning("Target repo NOT configured - Claude will run in current directory")

    # Stream response
    async def execution_loop(generator) -> AsyncGenerator[dict, None]:
        # Emit session info
        yield reasoning_step(
            event_type="INFO",
            message="Session started",
            details={
                "session_id": session.session_id,
                "is_continued": session.is_continued,
            },
        ).model_dump()

        # Emit context info if present
        if context.has_widget_context():
            widget_names = [w.name for w in context.primary_widgets]
            yield reasoning_step(
                event_type="INFO",
                message=f"Widget context: {', '.join(widget_names)}",
                details={"widget_count": len(context.primary_widgets)},
            ).model_dump()

        if context.has_tool_results():
            yield reasoning_step(
                event_type="INFO",
                message=f"Tool results available: {len(context.tool_results)}",
                details={
                    "functions": [t.function for t in context.tool_results],
                },
            ).model_dump()

        # Check target repo
        repo_ok, repo_msg = check_target_repo()
        if not repo_ok:
            yield reasoning_step(
                event_type="WARNING",
                message="Target repo not configured",
                details={"info": repo_msg},
            ).model_dump()
            yield message_chunk(
                "**Note:** Target workspace repo is not configured. "
                f"{settings.code_generator.capitalize()} will run in current directory. "
                "Set `OPENBB_APP_BUILDER_TARGET_REPO_PATH` for full app building.\n\n"
            ).model_dump()

        # Build prompt based on session state
        if session.is_continued:
            prompt = build_continuation_prompt(context)
        else:
            prompt = build_prompt(context, include_system=True)

        # Configure code generator
        generator_config = CodeGeneratorConfig(
            working_directory=str(settings.resolved_target_repo)
            if settings.resolved_target_repo
            else None,
            timeout=settings.claude_timeout,
            skip_permissions=settings.claude_skip_permissions,
        )

        # Execute code generator and stream results
        async for event in generator.run(prompt, session, generator_config):
            yield event

    return EventSourceResponse(
        content=execution_loop(generator),
        media_type="text/event-stream",
    )


@agent_router.post("/terminate")
async def terminate() -> JSONResponse:
    """Terminate any running Claude Code process."""
    was_terminated = await session_manager.terminate_current_process()
    return JSONResponse(
        content={
            "terminated": was_terminated,
            "message": "Process terminated" if was_terminated else "No process running",
        }
    )


@agent_router.post("/clear-sessions")
async def clear_sessions() -> JSONResponse:
    """Clear all session tracking data."""
    count = session_manager.clear_all_sessions()
    return JSONResponse(
        content={
            "cleared": count,
            "message": f"Cleared {count} sessions",
        }
    )


@agent_router.get("/sessions")
def list_sessions() -> JSONResponse:
    """List all active sessions (debugging endpoint)."""
    sessions = session_manager.list_sessions()
    return JSONResponse(
        content={
            "count": len(sessions),
            "sessions": sessions,
        }
    )


@agent_router.get("/models")
async def list_models() -> JSONResponse:
    """Get available LLM models for the configured code generator.

    For OpenCode: queries the OpenCode server /provider API to discover
    all configured models from supported providers.

    For Claude Code: returns a curated list of known Claude models,
    augmented with the user's configured model from ~/.claude/settings.json.
    """
    try:
        generator = get_code_generator(settings.code_generator)
        models = await generator.list_models()
        return JSONResponse(
            content={
                "generator": settings.code_generator,
                "models": [
                    {"id": m.id, "name": m.name, "provider": m.provider}
                    for m in models
                ],
            }
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e), "models": []},
        )
    except Exception as e:
        logger.exception("Failed to list models")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "models": []},
        )
