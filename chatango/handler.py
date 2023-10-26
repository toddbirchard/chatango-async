"""Async event handler."""
import sys
import asyncio
import traceback
from collections.abc import Iterable
from typing import Coroutine

from logger import LOGGER


class TaskHandler:
    """Handle, store, and track tasks."""

    @property
    def tasks(self):
        assert self.task_loop
        if not hasattr(self, "_tasks"):
            self._tasks = []
        return self._tasks

    @property
    def task_loop(self):
        """Main task loop which is started automatically."""
        if not hasattr(self, "_task_loop") or not self.task_loop:
            self.task_loop = asyncio.create_task(self.tasks_forever())
        return self.task_loop

    def add_task(self, coro: Coroutine):
        """Add and run a new task."""
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def _delayed_task(self, delay_time, coro: Coroutine):
        """Convenience wrapper for sleep before a task."""
        await asyncio.sleep(delay_time)
        await coro

    def add_delayed_task(self, delay_time, coro: Coroutine):
        """Queue task that will start after some time."""
        self.add_task(self._delayed_task(delay_time, coro))

    def cancel_tasks(self):
        """Cancel all remaining tasks."""
        for task in self.tasks:
            task.cancel()

    def end_tasks(self):
        """Purge all tasks and cancel task loop."""
        self.cancel_tasks()
        self.task_loop.cancel()

    def _prune_tasks(self):
        """Remove all done tasks, and log any exceptions if present."""
        for task in self.tasks:
            if task.done():
                if task.exception():
                    self._on_task_exception(task)
                    # Run as a one-off task in case it throws an exception itself
                    asyncio.create_task(self.on_task_exception(task))
                self.tasks.remove(task)

    def _on_task_exception(self, task: asyncio.Task):
        """Default behavior when a task results in an exception."""
        LOGGER.error(f"Exception in task: {repr(task.get_coro())}")
        task.print_stack(file=sys.stderr)

    async def on_task_exception(self, task: asyncio.Task):
        """Callback for custom behavior on task errors."""
        pass

    async def tasks_forever(self):
        """Infinite loop to keep task maintenance for the life of object."""
        while True:
            self._prune_tasks()
            await asyncio.sleep(1)

    async def complete_tasks(self):
        """Loop to watch tasks and exit when all are completed."""
        while self.tasks:
            self._prune_tasks()
            await asyncio.gather(*self.tasks)
            await asyncio.sleep(0.1)


class EventHandler(TaskHandler):
    """
    All objects listening here for events
    """

    @property
    def listeners(self):
        if not hasattr(self, "_listeners"):
            self._listeners = set()
        return self._listeners

    def add_listener(self, listener):
        """Add a listener for our events."""
        self.listeners.add(listener)

    def call_event(self, event: str, *args, **kwargs):
        """Trigger an event &  callback methods on this object."""
        attr = f"on_{event}"
        self._log_event(event, *args, **kwargs)
        # Call a generic event handler for all events
        if hasattr(self, "on_event"):
            self.add_task(getattr(self, "on_event")(event, *args, **kwargs))
        # Call the event handler on self
        if hasattr(self, attr):
            self.add_task(getattr(self, attr)(*args, **kwargs))
        # Call the same handlers on any listeners, passing self as first arg
        if self.listeners and isinstance(self.listeners, Iterable):
            for listener in self.listeners:
                if isinstance(listener, TaskHandler):
                    target = listener
                else:
                    target = self
                if hasattr(listener, "on_event"):
                    target.add_task(getattr(listener, "on_event")(self, event, *args, **kwargs))
                if hasattr(listener, attr):
                    target.add_task(getattr(listener, attr)(self, *args, **kwargs))

    def _log_event(self, event: str, *args, **kwargs):
        if len(args) == 0:
            args_section = ""
        elif len(args) == 1:
            args_section = args[0]
        else:
            args_section = repr(args)
        kwargs_section = "" if not kwargs else repr(kwargs)
        LOGGER.debug(f"EVENT {event} {args_section} {kwargs_section}")


class CommandHandler:
    """Handle command using the protocol of subclass (websocket, tcp, etc.)"""

    async def _send_command(self, *args, **kwargs):
        raise TypeError("CommandHandler child class must implement _send_command")

    async def send_command(self, *args):
        """Public send method."""
        command = ":".join(args)
        LOGGER.debug(f"OUT {command}")
        await self._send_command(command)

    async def _receive_command(self, command: str):
        """Receive an incoming command and call a handler."""
        if not command:
            return
        LOGGER.debug(f" IN {command}")
        action, *args = command.split(":")
        if hasattr(self, f"_rcmd_{action}"):
            try:
                await getattr(self, f"_rcmd_{action}")(args)
            except Exception as e:
                LOGGER.error(f"Error while handling command {action}")
                traceback.print_exception(e, file=sys.stderr)
        else:
            LOGGER.error(f"Unhandled received command {action}")
