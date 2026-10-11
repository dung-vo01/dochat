import logging


def setup_logging() -> None:
    """One line per event, key=value friendly, so it's greppable in Railway/Render logs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # OpenAI client is chatty
