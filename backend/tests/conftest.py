"""Test environment.

Settings are read at import time, and a developer's real .env holds a live OpenAI key
and a real database URL. Environment variables beat .env in pydantic-settings, so
pin safe dummies *before* any app module is imported: the suite can then never reach
the network, the real database, or the real vector store.
"""

import os
import tempfile

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:1/test"
os.environ["ALLOW_ORIGINS"] = "http://localhost:3000, https://example.vercel.app"
os.environ["OPENAI_API_KEY"] = "sk-test-not-a-real-key"
os.environ["OPENAI_MODEL"] = "test-model"
os.environ["OPENAI_EMBED_MODEL"] = "test-embed-model"
os.environ["CHROMA_PATH"] = tempfile.mkdtemp(prefix="dochat-test-chroma-")
