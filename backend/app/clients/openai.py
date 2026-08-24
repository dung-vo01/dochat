from openai import AsyncOpenAI

from app.core.config import settings

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

CHAT_MODEL = settings.OPENAI_MODEL
EMBED_MODEL = settings.OPENAI_EMBED_MODEL
