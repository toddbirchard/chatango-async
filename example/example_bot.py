"""Bot implementation demo."""
from chatango import Client, Room, Message

from logger import LOGGER


class Bot(Client):
    """Example Chatango Bot Implementation."""

    async def on_init(self):
        """Action upon bot initialization."""
        LOGGER.info("Bot initialized.")

    async def on_disconnect(self, room):
        """Action upon bot disconnection from a room."""
        LOGGER.warning(f"Disconnected from {repr(room)}")

    async def on_room_denied(self, room: Room):
        """
        This event get out when a room is deleted.
        self.rooms.remove(room_name)
        """
        print(f"[info] Rejected from {repr(room)}, ROOM must be deleted.")

    async def on_room_init(self, room: Room):
        """Action upon room initialization."""
        if room.user.is_anon:
            room.set_font(name_color="000000", font_color="000000", font_face=1, font_size=11)
        else:
            await room.user.get_profile()
            await room.enable_bg()

    async def on_message(self, room: Room, message: Message):
        """
        Triggers upon chat message to parse commands.

        :param Room room: Room object where the message was received.
        :param Message message: Raw message object received from a user.

        :returns: None
        """
        chat_message = message.body
        user_name = message.room.user.name
        room_name = message.room.name
        if bool(message.ip) is True and message.body is not None:
            LOGGER.info(f"[{room_name}] [{user_name}] [{message.ip}]: {chat_message}")
        else:
            LOGGER.info(f"[{room_name}] [{user_name}] [no IP address]: {chat_message}")
