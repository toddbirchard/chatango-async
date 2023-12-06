"""Initialization of example Chatango `bot` client."""
from example.example_bot import Bot
from example.config import config


def init_bot_client():
    """Initialize bot with example credentials & configuration."""
    bot = Bot(
        username=config.CHATANGO_BOT_USERNAME,
        password=config.CHATANGO_BOT_PASSWORD,
        rooms=config.CHATANGO_TEST_ROOMS,
    )
    return bot
