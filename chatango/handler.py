"""Async event handler."""
import inspect
import logging


class EventHandler:
    """Event handler for Chatango."""

    async def on_event(self, event: str, *args, **kwargs):
        if "ping" in event or "pong" in event:
            return
        if len(args) == 0:
            args_section = ""
        elif len(args) == 1:
            args_section = args[0]
        else:
            args_section = repr(args)
        kwargs_section = "" if not kwargs else repr(kwargs)
        logging.getLogger(__name__).debug("EVENT %s %s %s", event, args_section, kwargs_section)

    async def call_event(self, event: str, *args, **kwargs):
        attr = f"on_{event}"
        await self.on_event(event, *args, **kwargs)
        if hasattr(self, attr):
            await getattr(self, attr)(*args, **kwargs)

    def event(self, func, name=None):
        assert inspect.iscoroutinefunction(func)
        if name is None:
            event_name = func.__name__
        else:
            event_name = name
        setattr(self, event_name, func)


class CommandHandler:
    """Command handler for Chatango messages."""

    async def _call_command(self, command: str, *args, **kwargs):
        """Call underlying Chatango command."""
        attr = f"_rcmd_{command}"
        await self.on_command(command, *args, **kwargs)
        if hasattr(self, attr):
            await getattr(self, attr)(*args, **kwargs)

    async def on_command(self, command: str, *args, **kwargs):
        """Log received commands."""
        logging.getLogger(__name__).debug("%s %s %s", command, repr(args), repr(kwargs))

    async def _call_command(self, command: str, *args, **kwargs):
        """Call underlying Chatango command."""
        attr = f"_rcmd_{command}"
        await self.on_command(command, *args, **kwargs)
        if hasattr(self, attr):
            await getattr(self, attr)(*args, **kwargs)
