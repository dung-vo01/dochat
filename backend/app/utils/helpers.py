import io
import re
from dataclasses import dataclass

from pypdf import PdfReader

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150

# A sentence ends at . ! ? followed by whitespace; blank lines also separate blocks.
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n{2,}")


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int  # 1-based page number the chunk came from
    index: int  # position of the chunk within the whole document


def extract_pages(data: bytes) -> list[str]:
    """Return the text of each page; list index + 1 is the page number."""
    reader = PdfReader(io.BytesIO(data))
    return [page.extract_text() or "" for page in reader.pages]


def extract_text_from_pdf(data: bytes) -> str:
    return "\n".join(extract_pages(data))


def _split_sentences(text: str, size: int) -> list[str]:
    """Sentences, with any single over-long sentence hard-split at spaces."""
    pieces: list[str] = []

    for sentence in (s.strip() for s in SENTENCE_BOUNDARY.split(text)):
        while len(sentence) > size:
            cut = sentence.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)

    return pieces


def chunk_text(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Pack whole sentences into chunks of at most ~`size` chars.

    Chunks never cut a sentence in half (a fact like "...at least 99.0%, the
    customer receives a credit of 10%" stays together), and each chunk starts with
    up to `overlap` chars of trailing sentences from the previous one so a
    reference to "it" or "that plan" keeps its subject.
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[str] = []
    current: list[str] = []

    def length(parts: list[str]) -> int:
        return sum(len(p) for p in parts) + max(len(parts) - 1, 0)

    for sentence in _split_sentences(text.strip(), size):
        if current and length(current) + 1 + len(sentence) > size:
            chunks.append(" ".join(current))

            carried: list[str] = []
            for previous in reversed(current):
                if length([previous, *carried]) > overlap:
                    break
                carried.insert(0, previous)
            current = carried

            # Overlap must never push a new sentence past the size limit.
            while current and length(current) + 1 + len(sentence) > size:
                current.pop(0)

        current.append(sentence)

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_pages(
    pages: list[str], size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[Chunk]:
    """Chunk page by page so every chunk keeps its page number (used for citations)."""
    chunks: list[Chunk] = []

    for page_number, page_text in enumerate(pages, start=1):
        for text in chunk_text(page_text, size, overlap):
            chunks.append(Chunk(text=text, page=page_number, index=len(chunks)))

    return chunks
