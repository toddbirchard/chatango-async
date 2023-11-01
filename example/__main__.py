"""Entry point for the example bot."""
import asyncio
from example.example_bot import Bot
from config import config


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = Bot(config.CHATANGO_BOT_USERNAME, config.CHATANGO_BOT_PASSWORD, [config.CHATANGO_ROOMS])

    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        print("[KeyboardInterrupt] Killed bot.")
    finally:
        loop.stop()
        loop.close()
