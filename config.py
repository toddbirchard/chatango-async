import asyncio
import typing
from config import Config
import chatango


class MyBot(chatango.Client):
    """Example Chatango Bot Implementation."""

    async def on_init(self):
        """Action upon bot initialization."""
        print("Bot initialized.")

    async def on_start(self):
        """Action upon bot start."""
        if Config.rooms:
            for room in Config.rooms:
                task = self.join(room)
                await asyncio.ensure_future(task)
            await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
            print("[info] Bot has joined sucessfully all the rooms")
        else:
            print("[info] config.rooms is empty.")

    async def on_connect(self, room: typing.Union[chatango.Room, chatango.PM]):
        """Action upon bot connection to a room."""
        print(f"[info] Connected to {repr(room)}")

    async def on_disconnect(self, room):
        """Action upon bot disconnection from a room."""
        print(f"[info] Disconnected from {repr(room)}")

    async def on_room_denied(self, room):
        """
        This event get out when a room is deleted.
        self.rooms.remove(room_name)
        """
        print(f"[info] Rejected from {repr(room)}, ROOM must be deleted.")

    async def on_room_init(self, room):
        if room.user.isanon:
            room.set_font(name_color="000000", font_color="000000", font_face=1, font_size=11)
        else:
            await room.user.get_profile()
            await room.enable_bg()

    async def on_message(self, message):
        """
        Triggers upon chat message to parse commands.

        :param Message message: Raw message object received from a user.

        :returns: None
        """
        chat_message = message.body
        user_name = message.room.user.name
        room_name = message.room.name
        if bool(message.ip) is True and message.body is not None:
            print(f"[{room_name}] [{user_name}] [{message.ip}]: {chat_message}")
        else:
            print(f"[{room_name}] [{user_name}] [no IP address]: {chat_message}")
        

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = MyBot()
    bot.default_user(Config.botuser[0], Config.botuser[1])  # easy_start
    activate_pm_if_password = True if Config.botuser[1] else False
    ListBots = [bot.start(pm=activate_pm_if_password)]  # Multiple instances
    task = asyncio.gather(*ListBots, return_exceptions=True)
    try:
        loop.run_until_complete(task)
        loop.run_forever()
    except Exception as e:
        print(f"Fatal exception: {e}")
    finally:
        task.cancel()
        loop.close()
