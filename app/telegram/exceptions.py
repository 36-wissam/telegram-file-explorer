"""Telegram configuration and client exceptions."""


class TelegramAppError(Exception):
    """Base exception for all Telegram File Explorer errors."""
    pass


class ConfigurationError(TelegramAppError):
    """Raised when Telegram configuration is invalid or missing."""
    pass


class MissingCredentialsError(ConfigurationError):
    """Raised when either API ID or API Hash is missing."""

    def __init__(self, message: str = "Telegram API ID and API Hash are required."):
        super().__init__(
            f"{message}\n"
            "Please obtain your API ID and API Hash from https://my.telegram.org "
            "(under API development tools) and configure them in settings or the .env file."
        )


class InvalidApiIdError(ConfigurationError):
    """Raised when API ID format is invalid."""

    def __init__(self, api_id, message: str = "Telegram API ID must be a positive integer."):
        super().__init__(f"{message} Received: {api_id!r}")


class InvalidApiHashError(ConfigurationError):
    """Raised when API Hash format is invalid."""

    def __init__(self, api_hash, message: str = "Telegram API Hash must be a valid 32-character hexadecimal string."):
        super().__init__(f"{message} Received: {api_hash!r}")


class TelegramClientError(TelegramAppError):
    """Raised when an error occurs in the Telethon client lifecycle."""
    pass
