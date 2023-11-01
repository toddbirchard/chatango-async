"""Objects to use for testing."""
import pytest
from example.example_bot import Bot
from config import config


@pytest.fixture
def bot():
    """Return a bot instance."""
    return Bot(config.CHATANGO_BOT_USERNAME, config.CHATANGO_BOT_PASSWORD, [config.CHATANGO_ROOMS])
