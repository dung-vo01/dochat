import pytest

from app.utils.helpers import chunk_pages, chunk_text

SENTENCES = [
    "Annual plans can be refunded in full within 30 days of the invoice date.",
    "After 30 days no refund is available.",
    "Monthly plans are not refundable once the billing period has started.",
    "Approved refunds are returned to the original payment method within 10 business days.",
]
TEXT = " ".join(SENTENCES)


def test_chunks_never_exceed_size():
    chunks = chunk_text(TEXT * 5, size=200, overlap=50)
    assert chunks
    assert all(len(c) <= 200 for c in chunks)


def test_chunks_never_cut_a_sentence_in_half():
    chunks = chunk_text(TEXT * 3, size=200, overlap=0)
    for chunk in chunks:
        assert chunk.endswith("."), f"chunk ends mid-sentence: {chunk!r}"


def test_all_content_is_preserved():
    chunks = chunk_text(TEXT, size=150, overlap=0)
    assert " ".join(chunks) == TEXT


def test_overlap_carries_trailing_sentence_into_next_chunk():
    chunks = chunk_text(TEXT, size=170, overlap=80)
    assert len(chunks) >= 2
    # the last sentence of chunk N reappears at the start of chunk N+1
    last_sentence = chunks[0].split(". ")[-1]
    assert chunks[1].startswith(last_sentence.rstrip("."))


def test_overlap_never_pushes_a_chunk_past_the_limit():
    chunks = chunk_text(TEXT * 4, size=120, overlap=100)
    assert all(len(c) <= 120 for c in chunks)


def test_overlong_sentence_is_hard_split_at_spaces():
    sentence = " ".join(["word"] * 200) + "."
    chunks = chunk_text(sentence, size=100, overlap=0)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    assert all(not c.startswith(" ") and not c.endswith(" ") for c in chunks)


def test_empty_and_whitespace_text_give_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_text("anything", size=100, overlap=100)


def test_chunk_pages_keeps_page_numbers_and_global_index():
    pages = ["First page sentence. Another one.", "", "Third page sentence."]
    chunks = chunk_pages(pages, size=500, overlap=50)

    assert [c.page for c in chunks] == [1, 3]  # the empty page produces nothing
    assert [c.index for c in chunks] == [0, 1]
