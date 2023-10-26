"""Chatango-specific exceptions."""


class BaseRoomError(Exception):
    """Base exception for Chatango room errors."""

    room_name: str

    def __init__(self, room_name: str):
        super().__init__(room_name)
        self.room_name = room_name


class AlreadyConnectedError(BaseRoomError):
    """Raised when attempting to connect to a room that is already connected to."""
    pass


class NotConnectedError(BaseRoomError):
    """Raised when attempting to disconnect from a room that is not connected to."""
    pass


class InvalidRoomNameError(BaseRoomError):
    """Raised when attempting to connect to a room with an invalid name."""
    pass
