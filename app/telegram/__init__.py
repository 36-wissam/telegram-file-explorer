"""Telegram client integration package."""

from .client import TelegramClientManager, validate_api_credentials
from .exceptions import (
    ConfigurationError,
    InvalidApiHashError,
    InvalidApiIdError,
    MissingCredentialsError,
    TelegramAppError,
    TelegramClientError,
)

__all__ = [
    "TelegramClientManager",
    "validate_api_credentials",
    "TelegramAppError",
    "ConfigurationError",
    "MissingCredentialsError",
    "InvalidApiIdError",
    "InvalidApiHashError",
    "TelegramClientError",
]
