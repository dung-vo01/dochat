import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai import openai_client
from app.services.memory import clear_messages

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Returns the current date and time in UTC. Use when the user asks about the current date, time, or day.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Use when the user asks about recent events, news, or live data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_chat_history",
            "description": "Clears the current conversation history when the user asks to reset or start over.",
            "parameters": {
                "type": "object",
                "properties": {"conversation_id": {"type": "integer"}},
                "required": ["conversation_id"],
            },
        },
    },
]


def handle_get_current_datetime(**kwargs) -> str:
    now = datetime.now(UTC)
    return json.dumps(
        {
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
        }
    )


async def handle_web_search(query: str, **kwargs) -> str:
    try:
        response = await openai_client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=query,
        )
        return response.output_text
    except Exception as e:
        return json.dumps({"error": f"Web search failed: {e!s}"})


async def handle_clear_chat_history(
    conversation_id: int, db: AsyncSession, **kwargs
) -> str:
    try:
        await clear_messages(db, conversation_id)
        return json.dumps({"success": True, "message": "Chat history cleared."})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


async def execute_tool(name: str, arguments: dict, db: AsyncSession) -> str:
    handlers = {
        "get_current_datetime": handle_get_current_datetime,
        "web_search": handle_web_search,
        "clear_chat_history": handle_clear_chat_history,
    }
    handler = handlers.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})

    result = handler(db=db, **arguments)

    # await if the handler is async
    if asyncio.iscoroutine(result):
        return await result

    return result
