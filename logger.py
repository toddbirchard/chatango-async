"""Custom logger and error notifications."""
import json
import re
from sys import stdout

from loguru import logger


def json_formatter(record: dict) -> str:
    """
    Format info message logs.

    :param dict record: Log object containing log metadata & message.

    :returns: str
    """

    record["time"] = record["time"].strftime("%m/%d/%Y, %H:%M:%S")
    record["elapsed"] = record["elapsed"].total_seconds()

    def serialize_as_admin(log: dict) -> str:
        """
        Construct JSON info log record where user is room admin.

        :param dict log: Dictionary containing logged message with metadata.

        :returns: str
        """
        try:
            chat_data = re.search(r"(?P<room>\[\S+]) (?P<user>\[\S+]) (?P<ip>\[\S+])", log.get("message"))
            if chat_data and log.get("message"):
                subset = {
                    "time": log["time"],
                    "message": log["message"].split(": ", 1)[1],
                    "level": log["level"].name,
                    "room": chat_data["room"].replace("[", "").replace("]", ""),
                    "user": chat_data["user"].replace("[", "").replace("]", ""),
                    "ip": chat_data["ip"].replace("[", "").replace("]", ""),
                }
                return json.dumps(subset)
        except Exception as e:
            subset["error"] = f"Logging error occurred: {str(e)}"
            return serialize_error(subset)

    def serialize_event(log: dict) -> str:
        """
        Construct warning log.

        :param dict log: Dictionary containing logged message with metadata.

        :returns: str
        """
        try:
            chat_data = re.search(r"(?P<room>\[\S+]) (?P<user>\[\S+])", log["message"])
            if bool(chat_data) and log.get("message") is not None:
                subset = {
                    "time": log["time"],
                    "message": log["message"].split(": ", 1)[1],
                    "level": log["level"].name,
                    "room": chat_data["room"].replace("[", "").replace("]", ""),
                    "user": chat_data["user"].replace("[", "").replace("]", ""),
                }
                return json.dumps(subset)
        except Exception as e:
            log["error"] = f"Logging error occurred: {str(e)}"

    def serialize_error(log: dict) -> str:
        """
        Construct error log record.

        :param dict log: Dictionary containing logged message with metadata.

        :returns: str
        """
        if log and log.get("message"):
            subset = {
                "time": log["time"],
                "level": log["level"].name,
                "message": log["message"],
            }
            return json.dumps(subset)

    if record["level"].name == "INFO":
        record["extra"]["serialized"] = serialize_as_admin(record)
        return "{extra[serialized]},\n"
    if record["level"].name in ("TRACE", "WARNING", "SUCCESS", "DEBUG"):
        record["extra"]["serialized"] = serialize_event(record)
        return "{extra[serialized]},\n"
    if record["level"].name in ("ERROR", "CRITICAL"):
        record["extra"]["serialized"] = serialize_error(record)
        return "{extra[serialized]},\n"
    record["extra"]["serialized"] = serialize_error(record)
    return "{extra[serialized]},\n"


def log_formatter(record: dict) -> str:
    """
    Formatter for .log records

    :param dict record: Key/value object containing log message & metadata.

    :returns: str
    """
    if record["level"].name == "TRACE":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #d2eaff>{level}</fg #d2eaff>: <light-white>{message}</light-white>\n"
    if record["level"].name == "INFO":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #98bedf>{level}</fg #98bedf>: <light-white>{message}</light-white>\n"
    if record["level"].name == "WARNING":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> |  <fg #b09057>{level}</fg #b09057>: <light-white>{message}</light-white>\n"
    if record["level"].name == "SUCCESS":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #6dac77>{level}</fg #6dac77>: <light-white>{message}</light-white>\n"
    if record["level"].name == "ERROR":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #a35252>{level}</fg #a35252>: <light-white>{message}</light-white>\n"
    if record["level"].name == "CRITICAL":
        return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #521010>{level}</fg #521010>: <light-white>{message}</light-white>\n"
    return "<fg #5278a3>{time:MM-DD-YYYY HH:mm:ss}</fg #5278a3> | <fg #98bedf>{level}</fg #98bedf>: <light-white>{message}</light-white>\n"


def create_logger() -> logger:
    """
    Configure custom logger.

    :returns: logger
    """
    logger.remove()
    logger.add(stdout, level="TRACE", colorize=True, catch=True, format=log_formatter)
    return logger


LOGGER = create_logger()
