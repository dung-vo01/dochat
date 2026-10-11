import pytest

from app.core.config import Settings

BASE = {
    "ALLOW_ORIGINS": "http://localhost:3000",
    "OPENAI_API_KEY": "sk-test",
    "OPENAI_MODEL": "m",
    "OPENAI_EMBED_MODEL": "e",
}


def settings_with(**overrides) -> Settings:
    return Settings(_env_file=None, **{**BASE, **overrides})


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@host:5432/db",  # Heroku / older Railway
        "postgresql://u:p@host:5432/db",  # Railway / Render
        "postgresql+asyncpg://u:p@host:5432/db",  # already correct: left alone
    ],
)
def test_hosted_postgres_urls_get_the_async_driver(url):
    assert (
        settings_with(DATABASE_URL=url).DATABASE_URL
        == "postgresql+asyncpg://u:p@host:5432/db"
    )


def test_allowed_origins_accepts_a_comma_separated_list():
    s = settings_with(
        DATABASE_URL="postgresql://u:p@h/d",
        ALLOW_ORIGINS=" http://localhost:3000 , https://dochat.vercel.app ,",
    )
    assert s.allowed_origins == ["http://localhost:3000", "https://dochat.vercel.app"]
