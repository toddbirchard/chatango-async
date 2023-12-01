"""Initialization of example Chatango `bot` client."""
import asyncio
from example.example_bot import Bot
from config import config


def run_bot():
    """Initialize bot with example credentials & configuration."""
    try:
        # Build bot client
        bot = init_bot_client()

        # Create bot event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt as e:
        print(f"KeyboardInterrupt killed bot: {e}")
    except Exception as e:
        print(f"Unexpected Exception killed bot: {e}")
    finally:
        loop.stop()
        loop.close()


def init_bot_client():
    """Initialize bot with example credentials & configuration."""
    bot = Bot(
        username=config.CHATANGO_BOT_USERNAME,
        password=config.CHATANGO_BOT_PASSWORD,
        rooms=config.CHATANGO_TEST_ROOMS,
    )
    return bot
