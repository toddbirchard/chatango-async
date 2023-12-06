"""Example config values for tutorial."""
from os import getenv, path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


BASE_DIR = path.abspath(path.dirname(__file__))
load_dotenv(path.join(BASE_DIR, ".env"))


class Config(BaseSettings):
    """Chatango bot bare configuration."""

    ENVIRONMENT: str = getenv("ENVIRONMENT", "development")

    # Chatango
    # -------------------------------------------------

    # Chatango bot credentials
    CHATANGO_BOT_USERNAME: str = getenv("CHATANGO_BOT_USERNAME")
    CHATANGO_BOT_PASSWORD: str = getenv("CHATANGO_BOT_PASSWORD")

    # Chatango rooms to join
    CHATANGO_TEST_ROOMS: List[str] = [getenv("CHATANGO_TEST_ROOM")]


config = Config()
