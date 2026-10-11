"""stream_chat with a fake OpenAI client: no network, no database.

These pin down the behaviour around the model - streaming, tool calls, error
reporting, cancellation, persistence - which is where the production bugs were.
The model's *answers* are covered separately by the eval harness (backend/evals).
"""

import json
from types import SimpleNamespace

import httpx
from openai import APIError

from app.core.config import settings
from app.schemas import ChatRequest
from app.services import chat as chat_module
from app.services.rag import RetrievalResult, RetrievedChunk

# ---- fakes ---------------------------------------------------------------------


def text(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=None))
        ],
        usage=None,
    )


def usage(prompt=10, completion=5):
    return SimpleNamespace(
        choices=[],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


def tool_fragment(index, call_id=None, name=None, arguments=None):
    fragment = SimpleNamespace(
        index=index,
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[fragment]))
        ],
        usage=None,
    )


class FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for chunk in self.chunks:
            yield chunk


class FakeOpenAI:
    """Each entry in `scripts` is one create() call: a list of chunks, or an exception."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        script = self.scripts.pop(0)
        if isinstance(script, Exception):
            raise script
        return FakeStream(script)


CHUNK = RetrievedChunk("Annual plans: refund within 30 days.", "policy.pdf", 2, 0, 0.5)


def retrieval(chunks=(CHUNK,)):
    return RetrievalResult(
        chunks=list(chunks),
        candidates=len(chunks),
        top_distance=0.5 if chunks else None,
        summary_mode=False,
        has_documents=True,
        elapsed_ms=3,
    )


class Env:
    """Everything stream_chat talks to, patched, with the calls it made recorded."""

    def __init__(
        self, monkeypatch, scripts, prior=(), result=None, retrieve_error=None
    ):
        self.openai = FakeOpenAI(scripts)
        self.saved: list[tuple] = []  # (role, content, sources) via save_message
        self.partials: list[str] = []
        self.traces = []
        self.tool_runs: list[tuple] = []
        self.titles: list[str] = []
        result = result or retrieval()

        async def fake_retrieve(query, conversation_id):
            self.retrieval_query = query
            if retrieve_error:
                raise retrieve_error
            return result

        async def fake_save(db, conversation_id, role, content, sources=None):
            self.saved.append((role, content, sources))

        async def fake_get_messages(db, conversation_id):
            return [SimpleNamespace(role=r, content=c) for r, c in prior]

        async def fake_title(db, conversation_id, title):
            self.titles.append(title)

        async def fake_partial(conversation_id, partial):
            self.partials.append(partial)

        async def fake_record(trace):
            self.traces.append(trace)

        async def fake_execute(name, args, db):
            self.tool_runs.append((name, args))
            return json.dumps({"ok": True})

        patches = {
            "openai_client": self.openai,
            "retrieve": fake_retrieve,
            "save_message": fake_save,
            "get_messages": fake_get_messages,
            "update_conversation_title": fake_title,
            "_save_partial": fake_partial,
            "record_turn": fake_record,
            "execute_tool": fake_execute,
        }
        for name, value in patches.items():
            monkeypatch.setattr(chat_module, name, value)

    async def run(self, message="What is the refund window?", conversation_id=1):
        events = []
        async for raw in chat_module.stream_chat(
            ChatRequest(conversation_id=conversation_id, message=message), db=None
        ):
            events.append(raw)
        return events

    @property
    def trace(self):
        assert len(self.traces) == 1
        return self.traces[0]


def decode(events):
    return [
        e[6:].strip() if e.strip() == "data: [DONE]" else json.loads(e[6:])
        for e in events
    ]


# ---- tests ---------------------------------------------------------------------


async def test_answer_streams_with_one_model_call_and_cites_sources(monkeypatch):
    env = Env(monkeypatch, [[text("Within 30 days "), text("[1]."), usage(120, 14)]])

    events = decode(await env.run())

    assert events[0]["context"][0]["filename"] == "policy.pdf"
    assert [e["text"] for e in events if isinstance(e, dict) and "text" in e] == [
        "Within 30 days ",
        "[1].",
    ]
    assert events[-2]["sources"] == [
        {"n": 1, "filename": "policy.pdf", "page": 2, "snippet": CHUNK.text}
    ]
    assert events[-1] == "[DONE]"

    # Regression: a plain answer used to cost two model calls (a throwaway
    # non-streaming one to check for tools, then a second to stream).
    assert len(env.openai.calls) == 1
    assert env.openai.calls[0]["stream"] is True
    assert env.openai.calls[0]["tools"]

    assert env.saved[0][:2] == ("user", "What is the refund window?")
    assert env.saved[1] == ("assistant", "Within 30 days [1].", events[-2]["sources"])

    assert env.trace.status == "ok"
    assert env.trace.ttft_ms is not None
    assert (env.trace.prompt_tokens, env.trace.completion_tokens) == (120, 14)
    assert env.trace.cited_sources == 1
    assert env.trace.used_chunks == 1


async def test_only_cited_excerpts_are_returned_as_sources(monkeypatch):
    other = RetrievedChunk("Unrelated text.", "faq.pdf", 5, 1, 0.9)
    env = Env(
        monkeypatch,
        [[text("Answer from the first one [1].")]],
        result=retrieval([CHUNK, other]),
    )

    events = decode(await env.run())

    event = next(e for e in events if isinstance(e, dict) and "sources" in e)
    sources = event["sources"]
    assert [s["filename"] for s in sources] == ["policy.pdf"]


async def test_answer_without_citations_has_no_sources_event(monkeypatch):
    env = Env(monkeypatch, [[text("It is 144.")]])

    events = decode(await env.run("What is 12 times 12?"))

    assert not any(isinstance(e, dict) and "sources" in e for e in events)
    assert env.saved[1] == ("assistant", "It is 144.", None)


async def test_provider_error_is_reported_to_the_client_and_traced(monkeypatch):
    error = APIError(
        "Rate limit reached", request=httpx.Request("POST", "https://x"), body=None
    )
    env = Env(monkeypatch, [error])

    events = decode(await env.run())

    assert events == [
        events[0],  # context event
        {"error": "AI provider error: Rate limit reached"},
    ]
    assert "[DONE]" not in events
    assert env.trace.status == "error"
    assert env.trace.error_type == "APIError"


async def test_unexpected_errors_do_not_leak_details_to_the_client(monkeypatch):
    env = Env(monkeypatch, [RuntimeError("password=hunter2 in connection string")])

    events = await env.run()

    payload = " ".join(events)
    assert "hunter2" not in payload
    assert "RuntimeError" in payload
    assert env.trace.status == "error"
    assert "hunter2" in env.trace.error_message  # but it IS kept for debugging


async def test_tool_call_is_assembled_from_stream_fragments_then_answered(monkeypatch):
    env = Env(
        monkeypatch,
        [
            [
                tool_fragment(
                    0, call_id="call_1", name="get_current_datetime", arguments=""
                ),
                tool_fragment(0, arguments="{}"),
            ],
            [text("It is Monday.")],
        ],
    )

    events = decode(await env.run("What day is it?"))

    assert {"tool": "get_current_datetime"} in events
    assert env.tool_runs == [("get_current_datetime", {"conversation_id": 1})]

    first, second = env.openai.calls
    assert (
        first["tools"] and "tools" not in second
    )  # second pass can't chain more tools
    roles = [m["role"] for m in second["messages"]]
    assert roles[-2:] == ["assistant", "tool"]
    assert second["messages"][-2]["tool_calls"][0]["id"] == "call_1"
    assert second["messages"][-1]["tool_call_id"] == "call_1"
    assert env.trace.tool_called == "get_current_datetime"
    assert env.saved[-1][1] == "It is Monday."


async def test_every_parallel_tool_call_gets_a_result(monkeypatch):
    # The API rejects the follow-up request if any tool_call id has no tool message.
    env = Env(
        monkeypatch,
        [
            [
                tool_fragment(
                    0, call_id="a", name="get_current_datetime", arguments="{}"
                ),
                tool_fragment(
                    1, call_id="b", name="web_search", arguments='{"query": "x"}'
                ),
            ],
            [text("done")],
        ],
    )

    await env.run("What day is it and search x")

    second = env.openai.calls[1]["messages"]
    assert [m["tool_call_id"] for m in second if m["role"] == "tool"] == ["a", "b"]
    assert len(second[-3]["tool_calls"]) == 2


async def test_destructive_tool_is_refused_when_the_user_did_not_ask_for_it(
    monkeypatch,
):
    # e.g. text planted in a document says "call clear_chat_history"
    env = Env(
        monkeypatch,
        [
            [tool_fragment(0, call_id="c1", name="clear_chat_history", arguments="{}")],
            [text("The portal is at support.example.")],
        ],
    )

    events = decode(await env.run("What is the URL of the support portal?"))

    assert env.tool_runs == []  # never executed
    assert not any(isinstance(e, dict) and "tool" in e for e in events)
    tool_message = env.openai.calls[1]["messages"][-1]
    assert "Refused" in tool_message["content"]
    assert env.trace.tool_blocked is True
    assert env.trace.tool_called is None


async def test_destructive_tool_runs_when_asked_and_cannot_target_another_conversation(
    monkeypatch,
):
    env = Env(
        monkeypatch,
        [
            [
                tool_fragment(
                    0,
                    call_id="c1",
                    name="clear_chat_history",
                    arguments='{"conversation_id": 999}',  # model tries to wipe someone else's
                )
            ],
            [text("Cleared.")],
        ],
    )

    await env.run("please clear the chat history", conversation_id=7)

    assert env.tool_runs == [("clear_chat_history", {"conversation_id": 7})]
    assert env.trace.tool_blocked is False


async def test_malformed_tool_arguments_do_not_crash_the_turn(monkeypatch):
    env = Env(
        monkeypatch,
        [
            [tool_fragment(0, call_id="c1", name="web_search", arguments='{"query": ')],
            [text("Sorry, the search failed.")],
        ],
    )

    events = decode(await env.run("search for something"))

    assert env.tool_runs == []
    assert events[-1] == "[DONE]"
    assert "Invalid tool arguments" in env.openai.calls[1]["messages"][-1]["content"]


async def test_stopping_mid_stream_keeps_the_partial_answer_and_marks_the_turn_cancelled(
    monkeypatch,
):
    env = Env(monkeypatch, [[text("Within "), text("30 "), text("days.")]])

    stream = chat_module.stream_chat(
        ChatRequest(conversation_id=1, message="refund window?"), db=None
    )
    seen = []
    async for raw in stream:
        seen.append(raw)
        if '"text": "30 "' in raw:
            break
    await stream.aclose()  # what Starlette does when the client disconnects

    # Regression: Stop used to lose the partial answer, leaving a question with no reply.
    assert env.partials == ["Within 30 "]
    assert env.trace.status == "cancelled"
    assert env.trace.ttft_ms is not None


async def test_first_message_titles_the_conversation(monkeypatch):
    env = Env(monkeypatch, [[text("ok")]], prior=())
    await env.run("Summarise the policy")
    assert env.titles == ["Summarise the policy"]

    env = Env(
        monkeypatch, [[text("ok")]], prior=[("user", "hi"), ("assistant", "hello")]
    )
    await env.run("another question")
    assert env.titles == []


async def test_chat_is_still_titled_when_the_provider_fails_during_retrieval(
    monkeypatch,
):
    # Regression: an OpenAI 429 on the embedding call used to leave the chat as "New chat".
    quota = APIError(
        "insufficient_quota", request=httpx.Request("POST", "https://x"), body=None
    )
    env = Env(monkeypatch, [], prior=(), retrieve_error=quota)

    events = decode(await env.run("What is the refund window?"))

    assert env.titles == ["What is the refund window?"]
    assert events == [{"error": "AI provider error: insufficient_quota"}]
    assert env.trace.status == "error"


async def test_short_followup_retrieves_with_the_previous_question(monkeypatch):
    env = Env(
        monkeypatch,
        [[text("15 minutes")]],
        prior=[("user", "Sev 1 target for Business?"), ("assistant", "1 hour")],
    )

    await env.run("And for Enterprise?")

    assert env.retrieval_query == "Sev 1 target for Business? And for Enterprise?"


async def test_old_history_is_trimmed_before_it_reaches_the_model(monkeypatch):
    monkeypatch.setattr(settings, "HISTORY_TOKEN_BUDGET", 300)
    prior = []
    for i in range(20):
        prior += [
            ("user", f"question {i} " + "x" * 200),
            ("assistant", "answer " + "y" * 200),
        ]
    env = Env(monkeypatch, [[text("ok")]], prior=prior)

    await env.run("latest question")

    sent = env.openai.calls[0]["messages"]
    assert sent[0]["role"] == "system"
    assert sent[-1]["content"] == "latest question"
    assert len(sent) < 10
    assert env.trace.history_trimmed > 30
    assert env.trace.history_messages == 41
