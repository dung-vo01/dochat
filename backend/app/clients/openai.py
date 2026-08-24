from openai import OpenAI

from app.core.config import settings

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

CHAT_MODEL = settings.OPENAI_MODEL
EMBED_MODEL = settings.OPENAI_EMBED_MODEL
