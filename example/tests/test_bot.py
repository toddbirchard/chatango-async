"""Bot unit tests."""
import asyncio
from example.example_bot import Bot


def test_bot_init(bot: Bot):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(bot.run())
    assert isinstance(bot, Bot) is True
    loop.stop()
    loop.close()
