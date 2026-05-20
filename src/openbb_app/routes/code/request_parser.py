"""OpenBB request payload parser and normalizer.

Normalizes OpenBB QueryRequest into internal RequestContext objects
for consistent processing regardless of payload variations.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from openbb_ai.models import QueryRequest


@dataclass
class WidgetInfo:
    """Normalized widget metadata."""

    uuid: str
    widget_id: str
    name: str
    description: str = ""
    origin: str = "openbb"
    params: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WidgetInfo":
        """Create WidgetInfo from raw widget dict."""
        return cls(
            uuid=data.get("uuid", ""),
            widget_id=data.get("widget_id", data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            origin=data.get("origin", "openbb"),
            params=data.get("params", []),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "uuid": self.uuid,
            "widget_id": self.widget_id,
            "name": self.name,
            "description": self.description,
            "origin": self.origin,
            "params": self.params,
            "metadata": self.metadata,
        }


@dataclass
class ToolResult:
    """Normalized tool result data."""

    function: str
    input_arguments: dict[str, Any] = field(default_factory=dict)
    data: Any = None
    data_raw: Optional[str] = None
    extra_state: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_message(cls, msg: Any) -> Optional["ToolResult"]:
        """Create ToolResult from a tool message."""
        if not hasattr(msg, "role") or msg.role != "tool":
            return None

        data = None
        data_raw = None

        # Handle data field - could be string, dict, list, or Pydantic model
        if hasattr(msg, "data") and msg.data is not None:
            raw_data = msg.data
            if isinstance(raw_data, str):
                data_raw = raw_data
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    data = raw_data
            elif isinstance(raw_data, (dict, list)):
                data = raw_data
                try:
                    data_raw = json.dumps(raw_data)
                except (TypeError, ValueError):
                    data_raw = str(raw_data)
            elif hasattr(raw_data, "model_dump"):
                # Handle Pydantic models
                data = raw_data.model_dump()
                try:
                    data_raw = json.dumps(data)
                except (TypeError, ValueError):
                    data_raw = str(data)
            else:
                # Fallback for other types
                data = str(raw_data)
                data_raw = data

        return cls(
            function=getattr(msg, "function", "unknown"),
            input_arguments=getattr(msg, "input_arguments", {}) or {},
            data=data,
            data_raw=data_raw,
            extra_state=getattr(msg, "extra_state", {}) or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "function": self.function,
            "input_arguments": self.input_arguments,
            "data": self.data,
            "extra_state": self.extra_state,
        }


@dataclass
class RequestContext:
    """Normalized internal context from an OpenBB request.

    Provides a consistent interface for accessing:
    - User message and conversation history
    - Widget metadata (primary/secondary)
    - Tool results from prior messages
    """

    # Latest human message content
    user_message: str

    # Conversation history (list of role/content dicts)
    history: list[dict[str, Any]] = field(default_factory=list)

    # Primary widgets selected by user
    primary_widgets: list[WidgetInfo] = field(default_factory=list)

    # Secondary widgets (additional context)
    secondary_widgets: list[WidgetInfo] = field(default_factory=list)

    # Tool results from conversation
    tool_results: list[ToolResult] = field(default_factory=list)

    # Whether the last message is from a human (should execute)
    should_execute: bool = True

    # Raw request for debugging
    raw_request: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization/persistence."""
        return {
            "user_message": self.user_message,
            "history": self.history,
            "primary_widgets": [w.to_dict() for w in self.primary_widgets],
            "secondary_widgets": [w.to_dict() for w in self.secondary_widgets],
            "tool_results": [t.to_dict() for t in self.tool_results],
            "should_execute": self.should_execute,
        }

    def has_widget_context(self) -> bool:
        """Check if any widget context is available."""
        return bool(self.primary_widgets or self.secondary_widgets)

    def has_tool_results(self) -> bool:
        """Check if any tool results are available."""
        return bool(self.tool_results)


def parse_request(request: QueryRequest) -> RequestContext:
    """Parse OpenBB QueryRequest into normalized RequestContext.

    Args:
        request: The incoming OpenBB query request.

    Returns:
        Normalized RequestContext with extracted data.
    """
    # Extract messages
    messages = request.messages or []

    # Find latest human message
    user_message = ""
    should_execute = False
    history: list[dict[str, Any]] = []

    for msg in messages:
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", "")

        if role == "human":
            user_message = content if isinstance(content, str) else str(content)
            should_execute = True
            history.append({"role": "human", "content": user_message})
        elif role == "ai":
            # AI response - could be string or structured
            if isinstance(content, str):
                history.append({"role": "ai", "content": content})
            should_execute = False
        elif role == "tool":
            # Tool message resets execution flag if it's the last
            should_execute = False
            history.append({"role": "tool", "function": getattr(msg, "function", "")})

    # Check if last message is human
    if messages and hasattr(messages[-1], "role"):
        should_execute = messages[-1].role == "human"

    # Extract widgets
    primary_widgets: list[WidgetInfo] = []
    secondary_widgets: list[WidgetInfo] = []

    widgets = getattr(request, "widgets", None)
    if widgets:
        # Handle both dict and object access patterns
        if isinstance(widgets, dict):
            primary_list = widgets.get("primary", [])
            secondary_list = widgets.get("secondary", [])
        else:
            primary_list = getattr(widgets, "primary", []) or []
            secondary_list = getattr(widgets, "secondary", []) or []

        for w in primary_list:
            if isinstance(w, dict):
                primary_widgets.append(WidgetInfo.from_dict(w))
            else:
                primary_widgets.append(
                    WidgetInfo.from_dict(
                        {
                            "uuid": getattr(w, "uuid", ""),
                            "widget_id": getattr(w, "widget_id", ""),
                            "name": getattr(w, "name", ""),
                            "description": getattr(w, "description", ""),
                            "origin": getattr(w, "origin", "openbb"),
                            "params": getattr(w, "params", []),
                            "metadata": getattr(w, "metadata", {}),
                        }
                    )
                )

        for w in secondary_list:
            if isinstance(w, dict):
                secondary_widgets.append(WidgetInfo.from_dict(w))

    # Extract tool results
    tool_results: list[ToolResult] = []
    for msg in messages:
        result = ToolResult.from_message(msg)
        if result:
            tool_results.append(result)

    return RequestContext(
        user_message=user_message,
        history=history,
        primary_widgets=primary_widgets,
        secondary_widgets=secondary_widgets,
        tool_results=tool_results,
        should_execute=should_execute,
    )


def extract_conversation_id(request: QueryRequest) -> Optional[str]:
    """Extract or generate a conversation ID from request.

    OpenBB doesn't provide explicit conversation IDs, so we generate
    one from the first message hash.

    Args:
        request: The OpenBB query request.

    Returns:
        A conversation ID string, or None if no messages.
    """
    messages = request.messages or []
    if not messages:
        return None

    first_msg = messages[0]
    content = getattr(first_msg, "content", "")
    if content:
        # Use hash of first message as pseudo conversation ID
        return str(hash(content))[:16]

    return None
