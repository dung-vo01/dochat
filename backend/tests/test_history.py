from app.services.history import (
    cited_numbers,
    contextualise_query,
    estimate_tokens,
    trim_history,
)
from app.services.tools import tool_allowed


def msg(role: str, text: str) -> dict:
    return {"role": role, "content": text}


def test_trim_keeps_everything_when_under_budget():
    messages = [msg("user", "hi"), msg("assistant", "hello"), msg("user", "bye")]
    kept, dropped = trim_history(messages, budget=1000)
    assert kept == messages
    assert dropped == 0


def test_trim_drops_oldest_first():
    messages = [
        msg("user", "a" * 400),
        msg("assistant", "b" * 400),
        msg("user", "c" * 400),
    ]
    budget = estimate_tokens("c" * 400) + estimate_tokens("b" * 400)
    kept, dropped = trim_history(messages, budget)

    assert [m["content"][0] for m in kept] == ["b", "c"][-len(kept) :]
    assert dropped == 3 - len(kept)
    assert kept[-1]["content"].startswith("c")  # newest always survives


def test_trim_always_keeps_newest_even_if_it_alone_exceeds_budget():
    kept, dropped = trim_history([msg("user", "x" * 100_000)], budget=10)
    assert len(kept) == 1
    assert dropped == 0


def test_trim_does_not_open_with_an_orphaned_assistant_reply():
    messages = [msg("user", "q" * 400), msg("assistant", "a" * 40), msg("user", "q2")]
    budget = estimate_tokens("a" * 40) + estimate_tokens("q2")  # question 1 doesn't fit
    kept, _ = trim_history(messages, budget)
    assert kept[0]["role"] == "user"


def test_cited_numbers_parses_adjacent_and_comma_separated_citations():
    assert cited_numbers("Yes [1][3]. Also see [2, 4].") == [1, 2, 3, 4]


def test_cited_numbers_ignores_non_citations():
    assert cited_numbers("an array a[i] and [text] and (1)") == []


def test_short_followup_is_contextualised_with_previous_question():
    assert (
        contextualise_query(
            "And for Enterprise?", "What is the Sev 1 target for Business?"
        )
        == "What is the Sev 1 target for Business? And for Enterprise?"
    )


def test_long_or_first_messages_are_left_alone():
    long_message = (
        "What is the first-response target for a Severity 1 incident on Enterprise?"
    )
    assert contextualise_query(long_message, "previous question") == long_message
    assert contextualise_query("And for Enterprise?", None) == "And for Enterprise?"


def test_destructive_tool_needs_the_user_to_ask():
    assert tool_allowed("clear_chat_history", "please clear the chat history")
    assert tool_allowed("clear_chat_history", "Start over")
    assert not tool_allowed(
        "clear_chat_history", "What is the URL of the support portal?"
    )


def test_non_destructive_tools_are_not_gated():
    assert tool_allowed("get_current_datetime", "anything at all")
