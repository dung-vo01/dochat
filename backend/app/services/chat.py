import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import anyio
from openai import APIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai import CHAT_MODEL, openai_client
from app.core.config import settings
from app.db.session import async_session_maker
from app.schemas import ChatRequest
from app.services.history import cited_numbers, contextualise_query, trim_history
from app.services.memory import get_messages, save_message, update_conversation_title
from app.services.metrics import TurnTrace, record_turn
from app.services.rag import RetrievalResult, build_system_prompt, retrieve
from app.services.tools import TOOLS, execute_tool, tool_allowed

logger = logging.getLogger(__name__)

TOOL_TIMEOUT_S = 20
SNIPPET_CHARS = 240


def _sse(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"


def _context_event(result: RetrievalResult, full_text: bool) -> dict:
    """Everything retrieval put in the prompt, so the UI/evals can inspect it."""
    return {
        "context": [
            {
                "n": i,
                "filename": c.filename,
                "page": c.page,
                "distance": c.distance,
                "text": c.text if full_text else c.text[:SNIPPET_CHARS],
            }
            for i, c in enumerate(result.chunks, start=1)
        ]
    }


def _cited_sources(answer: str, result: RetrievalResult) -> list[dict]:
    """The excerpts the answer actually cited - not everything retrieved."""
    return [
        {
            "n": n,
            "filename": result.chunks[n - 1].filename,
            "page": result.chunks[n - 1].page,
            "snippet": result.chunks[n - 1].text[:SNIPPET_CHARS],
        }
        for n in cited_numbers(answer)
        if 1 <= n <= len(result.chunks)
    ]


async def _complete(messages: list[dict], trace: TurnTrace, use_tools: bool):
    """One streamed model call. Yields ("text", delta) as tokens arrive and, if the
    model asked for tools, a final ("tool_calls", [...]) once they're fully assembled.

    Streaming *with* tools enabled means a plain answer starts flowing immediately;
    the previous design made a separate non-streaming call first just to find out
    whether a tool was needed, then threw its answer away and asked again.
    """
    kwargs: dict = {
        "model": CHAT_MODEL,
        "messages": messages,
        "temperature": settings.OPENAI_TEMPERATURE,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if use_tools:
        kwargs.update(tools=TOOLS, tool_choice="auto")

    stream = await openai_client.chat.completions.create(**kwargs)
    calls: dict[int, dict] = {}

    async for chunk in stream:
        if chunk.usage:  # final chunk: no choices, just token counts
            trace.add_usage(chunk.usage)
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta
        if delta.content:
            yield "text", delta.content

        # Tool calls arrive as fragments keyed by index; stitch them together.
        for fragment in delta.tool_calls or []:
            slot = calls.setdefault(
                fragment.index, {"id": "", "name": "", "arguments": ""}
            )
            if fragment.id:
                slot["id"] = fragment.id
            if fragment.function:
                if fragment.function.name:
                    slot["name"] = fragment.function.name
                if fragment.function.arguments:
                    slot["arguments"] += fragment.function.arguments

    if calls:
        yield "tool_calls", [calls[i] for i in sorted(calls)]


async def _run_tool(
    call: dict, data: ChatRequest, db: AsyncSession, trace: TurnTrace
) -> str:
    name = call["name"]

    if not tool_allowed(name, data.message):
        # A destructive tool the user didn't ask for - most likely text planted in a
        # document. Refuse and tell the model why.
        trace.tool_blocked = True
        logger.warning("blocked tool call %s: not requested by the user", name)
        return json.dumps(
            {"error": "Refused: the user must explicitly ask for this action."}
        )

    try:
        args = json.loads(call["arguments"] or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid tool arguments"})

    # Always scope to this conversation; never let the model pick which one.
    args["conversation_id"] = data.conversation_id
    trace.tool_called = trace.tool_called or name

    try:
        return await asyncio.wait_for(
            execute_tool(name, args, db), timeout=TOOL_TIMEOUT_S
        )
    except TimeoutError:
        return json.dumps({"error": f"{name} timed out"})


async def _save_partial(conversation_id: int, text: str) -> None:
    """Persist what was streamed before a cancel/error, in a fresh session (the
    request's session may be mid-statement when the task is cancelled)."""
    try:
        async with async_session_maker() as session:
            await save_message(session, conversation_id, "assistant", text)
    except Exception:
        logger.exception("failed to save partial answer")


async def stream_chat(
    data: ChatRequest, db: AsyncSession, source: str = "app"
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings.

    Event types: context (retrieved excerpts), tool, text, sources (cited
    excerpts), error. The router has already checked the conversation exists -
    once streaming starts a 200 is on the wire, so failures here can only be
    reported as an "error" event.

    Every turn is traced to `chat_turns` (see services/metrics.py).
    """
    trace = TurnTrace(
        conversation_id=data.conversation_id, source=source, model=CHAT_MODEL
    )
    answer_parts: list[str] = []
    saved = False

    try:
        prior = await get_messages(db, data.conversation_id)
        previous_user = next(
            (m.content for m in reversed(prior) if m.role == "user"), None
        )

        # Needs no model call, so don't let a failing retrieval/provider leave the
        # chat titled "New chat".
        if not prior:
            await update_conversation_title(db, data.conversation_id, data.message)

        # Run save + RAG retrieval concurrently as they dont depend on each other
        result, _ = await asyncio.gather(
            retrieve(
                contextualise_query(data.message, previous_user), data.conversation_id
            ),
            save_message(db, data.conversation_id, "user", data.message),
        )
        trace.apply_retrieval(result)
        if result.chunks:
            yield _sse(_context_event(result, full_text=source == "eval"))

        history = [
            *({"role": m.role, "content": m.content} for m in prior),
            {"role": "user", "content": data.message},
        ]

        conversation, trimmed = trim_history(history, settings.HISTORY_TOKEN_BUDGET)
        trace.history_messages, trace.history_trimmed = len(history), trimmed

        messages: list[dict] = [
            {"role": "system", "content": build_system_prompt(result)},
            *conversation,
        ]

        pending: list[dict] | None = None
        async for kind, payload in _complete(messages, trace, use_tools=True):
            if kind == "text":
                trace.mark_first_token()
                answer_parts.append(payload)
                yield _sse({"text": payload})
            else:
                pending = payload

        if pending:
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(answer_parts) or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": c["arguments"] or "{}",
                            },
                        }
                        for c in pending
                    ],
                }
            )
            # The API requires a result for *every* tool call in the assistant message.
            for call in pending:
                if tool_allowed(call["name"], data.message):
                    yield _sse({"tool": call["name"]})
                output = await _run_tool(call, data, db, trace)
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": output}
                )

            async for kind, payload in _complete(messages, trace, use_tools=False):
                if kind == "text":
                    trace.mark_first_token()
                    answer_parts.append(payload)
                    yield _sse({"text": payload})

        answer = "".join(answer_parts)
        sources = _cited_sources(answer, result)
        trace.cited_sources = len(sources)

        await save_message(
            db, data.conversation_id, "assistant", answer, sources or None
        )
        saved = True

        if sources:
            yield _sse({"sources": sources})
        yield "data: [DONE]\n\n"

    except APIError as e:
        trace.fail(e, e.message)
        yield _sse({"error": f"AI provider error: {e.message}"})
    except (asyncio.CancelledError, GeneratorExit):
        trace.status = "cancelled"  # client pressed Stop / disconnected
        raise
    except Exception as e:
        logger.exception("chat turn failed")
        trace.fail(e, str(e))
        # Details stay in the logs/metrics; the client gets the class name only.
        yield _sse({"error": f"Unexpected error ({type(e).__name__})"})
    finally:
        # Cancellation is level-triggered under anyio, so shield the cleanup or every
        # await in here would be cancelled again immediately.
        with anyio.CancelScope(shield=True):
            if not saved and answer_parts:
                await _save_partial(data.conversation_id, "".join(answer_parts))
            await record_turn(trace)
