"""Bot implementation demo."""
import asyncio
from config import config
from chatango import Client, Room, User, Message


class MyBot(Client):
    """Example Chatango Bot Implementation."""

    async def on_connect(self, room: Room):
        print(f"Connected to {room}")
        await room.send_message("Beep boop I'm dead inside 🤖", use_html=True)

    async def on_init(self):
        """Action upon bot initialization."""
        print("Bot initialized.")

    async def on_start(self):
        """Action upon bot start."""
        if config.rooms:
            for room in config.rooms:
                task = room.join(room)
                await asyncio.ensure_future(task)
            await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
            print("[info] Bot has joined successfully all the rooms")
        else:
            print("[info] config.rooms is empty.")

    async def on_disconnect(self, room):
        """Action upon bot disconnection from a room."""
        print(f"[info] Disconnected from {repr(room)}")

    async def on_room_denied(self, room: Room):
        """
        This event get out when a room is deleted.
        self.rooms.remove(room_name)
        """
        print(f"[info] Rejected from {repr(room)}, ROOM must be deleted.")

    async def on_room_init(self, room: Room):
        """Action upon room initialization."""
        if room.user.isanon:
            room.set_font(name_color="000000", font_color="000000", font_face=1, font_size=11)
        else:
            await room.user.get_profile()
            await room.enable_bg()

    async def on_message(self, room: Room, message: Message):
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
