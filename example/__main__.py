"""Example entry point."""
import asyncio
from example import init_bot_client


if __name__ == "__main__":
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
