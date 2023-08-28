"""Top-level Chatango client handler."""
import asyncio
import logging
from typing import Coroutine, Dict, List, Optional

from .pm import PM
from .room import Room
from .handler import EventHandler
from .utils import public_attributes


logger = logging.getLogger(__name__)


class Client(EventHandler):
    """Chatango top-level client."""

    def __init__(self, username: str, password: str, rooms: List[str], pm: bool = False):
        self._tasks: List[asyncio.Task] = []
        self.running = False
        self.rooms: Dict[str, Room] = {}
        self.pm: Optional[PM] = None
        self.use_pm = pm
        self.initial_rooms: List[str] = rooms
        self.username = username
        self.password = password

    def __dir__(self):
        return public_attributes(self)

    def add_task(self, task: Coroutine):
        """
        Add async task to event loop.

        :param Coroutine task: Task to add to event loop.
        """
        self._tasks.append(asyncio.create_task(task))

    def _prune_tasks(self):
        """Remove completed tasks from event loop."""
        self._tasks = [task for task in self._tasks if not task.done()]

    async def _task_loop(self, forever=False):
        """Run tasks in event loop."""
        while self._tasks or forever:
            await asyncio.gather(*self._tasks)
            self._prune_tasks()
            if forever:
                await asyncio.sleep(0.1)

    async def run(self, *, forever=False):
        """Initialize client."""
        self.running = True
        await self.call_event("init")

        if not forever and not self.use_pm and not self.initial_rooms:
            logger.error("No rooms or PM to join. Exiting.")
            return

        if self.use_pm:
            self.join_pm()

        for room_name in self.initial_rooms:
            self.join_room(room_name)

        await self.call_event("start")
        await self._task_loop(forever)
        self.running = False

        return self.initial_rooms

    def join_pm(self):
        """Begin a PM session with a Chatango user."""
        if not self.username or not self.password:
            logger.error("PM requires username and password.")
            return

        self.add_task(self._watch_pm())

    async def _watch_pm(self):
        """Listen for activity in PM session."""
        pm = PM(self)
        self.pm = pm
        await pm.listen(self.username, self.password, reconnect=True)
        self.pm = None

    def leave_pm(self):
        """Disconnect from PM session."""
        if self.pm:
            self.add_task(self.pm.disconnect())

    def get_room(self, room_name: str) -> str:
        """
        Validate and return name of Chatango room.

        :param str room_name: Name of Chatango room.

        :returns: str
        """
        Room.assert_valid_name(room_name)
        return self.rooms.get(room_name)

    def in_room(self, room_name: str) -> List[str]:
        """
        Lit of Chatango room names client is currently connected to.

        :param str room_name: Name of Chatango room.

        :returns: List[str]
        """
        Room.assert_valid_name(room_name)
        return room_name in self.rooms

    async def join_room(self, room_name: str):
        """Connect to Chatango room."""
        Room.assert_valid_name(room_name)
        if self.in_room(room_name):
            logger.error(f"Already joined room {room_name}")
            # Attempt to reconnect existing room?
            return

        room_name = await self._watch_room(room_name)
        self.add_task(room_name)

    async def _watch_room(self, room_name: str):
        """Attempt to join Chatango room."""
        room = Room(self, room_name)
        self.rooms[room_name] = room
        await room.listen(self.username, self.password, reconnect=True)
        # Client level reconnect?
        self.rooms.pop(room_name, None)

    def leave_room(self, room_name: str):
        """
        Disconnect from Chatango room.

        :param str room_name: Name of Chatango room.
        """
        room = self.get_room(room_name)
        if room:
            self.add_task(room.disconnect())

    def stop(self):
        """Stop client."""
        if self.pm:
            self.leave_pm()

        for room_name in self.rooms:
            self.leave_room(room_name)

    async def enable_bg(self, active=True):
        """Enable background if available."""
        self.bgmode = active
        for _, room in self.rooms.items():
            await room.set_bg_mode(int(active))
