import asyncio
import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai import CHAT_MODEL, openai_client
from app.schemas import ChatRequest
from app.services.memory import (
    get_conversation,
    get_messages,
    save_message,
    update_conversation_title,
)
from app.services.rag import build_system_prompt, retrieve
from app.services.tools import TOOLS, execute_tool


def _sse(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"


async def stream_chat(data: ChatRequest, db: AsyncSession) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings.
    Raises ValueError if the conversation is not found — router handles the HTTP response.
    """
    conv = await get_conversation(db, data.conversation_id)
    if not conv:
        raise ValueError(f"Conversation {data.conversation_id} not found")

    # Run save + RAG retrieval concurrently as they dont depend on each other
    context_chunks, _ = await asyncio.gather(
        retrieve(data.message),
        save_message(db, data.conversation_id, "user", data.message),
    )

    history = await get_messages(db, data.conversation_id)

    if len(history) == 1:
        await update_conversation_title(db, data.conversation_id, data.message)

    system_prompt = build_system_prompt(context_chunks)
    full_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.role, "content": m.content} for m in history
    ]

    # Non-streaming pass to check for tool calls
    response = await openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=full_messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    message = response.choices[0].message

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        tool_args.setdefault("conversation_id", data.conversation_id)

        tool_result = await execute_tool(tool_name, tool_args, db)

        yield _sse({"tool": tool_name})

        full_messages += [
            message,
            {"role": "tool", "tool_call_id": tool_call.id, "content": tool_result},
        ]

    # Stream the final response
    stream = await openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=full_messages,
        stream=True,
    )

    full_response: list[str] = []
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_response.append(delta)
            yield _sse({"text": delta})

    await save_message(db, data.conversation_id, "assistant", "".join(full_response))
    yield "data: [DONE]\n\n"
