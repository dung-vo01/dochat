from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str

    @field_validator("DATABASE_URL")
    @classmethod
    def use_async_driver(cls, url: str) -> str:
        """Railway/Render/Heroku hand out postgres:// or postgresql:// URLs, but the
        async engine needs the asyncpg driver named in the scheme."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix) :]
        return url

    # Comma-separated list, e.g. "http://localhost:5173,https://dochat.vercel.app"
    ALLOW_ORIGINS: str
    OPENAI_API_KEY: str
    OPENAI_MODEL: str
    OPENAI_EMBED_MODEL: str

    # Low temperature: grounded Q&A should be repeatable, not creative.
    OPENAI_TEMPERATURE: float = 0.2

    CHROMA_PATH: str = "./chroma_db"

    # Ingestion
    # Chosen from evals/retrieval_sweep.py on two question sets: 300 loses recall;
    # 800+ mixes several topics into one embedding, so the right chunk can fall out
    # of the top 4 (held-out set: hit@4 88% at 800 vs 100% at 500).
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 150
    MAX_UPLOAD_MB: int = 10

    # Retrieval
    RETRIEVAL_TOP_K: int = 4
    # Optional L2-distance cutoff, OFF by default. The retrieval sweep showed distances
    # for correct chunks (0.5-1.5) fully overlap those of unanswerable questions
    # (0.8-1.4), so a threshold drops right answers without catching wrong ones.
    # Unanswerable questions are handled by the prompt + evals instead.
    RETRIEVAL_MAX_DISTANCE: float | None = None
    SUMMARY_MAX_CHUNKS: int = 24

    # Conversation memory (approximate tokens, ~4 chars each)
    HISTORY_TOKEN_BUDGET: int = 6000

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOW_ORIGINS.split(",") if o.strip()]


settings = Settings()
