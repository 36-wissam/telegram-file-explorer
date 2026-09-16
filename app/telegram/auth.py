"""Telegram authentication manager and service."""

import os
from enum import Enum
from typing import Optional, Dict, Any
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from ..core.config import settings
from ..core.logger import get_logger
from .client import TelegramClientManager
from .exceptions import TelegramAppError

logger = get_logger("telegram.auth")


class AuthState(str, Enum):
    """Authentication states for Telegram MTProto session."""
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DISCONNECTED = "DISCONNECTED"
    UNAUTHORIZED = "UNAUTHORIZED"
    WAITING_FOR_CODE = "WAITING_FOR_CODE"
    WAITING_FOR_PASSWORD = "WAITING_FOR_PASSWORD"
    AUTHORIZED = "AUTHORIZED"


class AuthError(TelegramAppError):
    """Base exception for authentication failures."""
    pass


class TelegramAuthService:
    """Handles the complete user authentication lifecycle with Telegram MTProto."""

    def __init__(self, client_manager: TelegramClientManager):
        self.manager = client_manager
        self.state: AuthState = AuthState.NOT_CONFIGURED
        self.phone_number: Optional[str] = None
        self.phone_code_hash: Optional[str] = None
        self.current_user: Optional[Dict[str, Any]] = None

    @property
    def client(self) -> Optional[TelegramClient]:
        """Return underlying Telethon client."""
        return self.manager.client

    async def check_auth_state(self) -> AuthState:
        """Connect to Telegram and detect the current authorization state.

        Detects if existing local session is still valid (session persistence)
        and auto-reconnects.
        """
        if not self.manager.settings.is_telegram_configured:
            self.state = AuthState.NOT_CONFIGURED
            return self.state

        if not self.manager.is_initialized:
            try:
                self.manager.initialize_client()
            except Exception as e:
                logger.error("Failed initializing client during state check: %s", e)
                self.state = AuthState.NOT_CONFIGURED
                return self.state

        client = self.manager.client
        try:
            if not client.is_connected():
                logger.info("Connecting to Telegram MTProto servers...")
                await client.connect()

            is_auth = await client.is_user_authorized()
            if is_auth:
                me = await client.get_me()
                self.current_user = {
                    "id": me.id,
                    "first_name": me.first_name or "",
                    "last_name": me.last_name or "",
                    "username": me.username or "",
                    "phone": me.phone or "",
                }
                self.state = AuthState.AUTHORIZED
                logger.info(
                    "Session successfully authenticated for user %s (@%s, ID: %s)",
                    self.current_user["first_name"],
                    self.current_user["username"],
                    self.current_user["id"],
                )
            else:
                self.state = AuthState.UNAUTHORIZED
                self.current_user = None
                logger.info("Session is not authorized. Ready for login.")

        except Exception as e:
            logger.error("Error checking auth state: %s", e)
            self.state = AuthState.DISCONNECTED

        return self.state

    async def send_code(self, phone_number: str) -> str:
        """Send login verification code (OTP) to the given phone number."""
        clean_phone = phone_number.strip().replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+"):
            clean_phone = f"+{clean_phone}"

        if not self.manager.is_initialized:
            self.manager.initialize_client()

        client = self.manager.client
        if not client.is_connected():
            await client.connect()

        logger.info("Requesting login code for %s...", clean_phone[:6] + "***")
        try:
            res = await client.send_code_request(clean_phone)
            self.phone_number = clean_phone
            self.phone_code_hash = res.phone_code_hash
            self.state = AuthState.WAITING_FOR_CODE
            logger.info("Verification code sent successfully.")
            return self.phone_code_hash
        except PhoneNumberInvalidError as e:
            raise AuthError("Invalid phone number. Please check country code format (e.g. +1234567890).") from e
        except PhoneNumberBannedError as e:
            raise AuthError("This phone number has been banned by Telegram.") from e
        except FloodWaitError as e:
            raise AuthError(f"Too many attempts. Please wait {e.seconds} seconds before trying again.") from e
        except Exception as e:
            logger.error("Failed sending code: %s", e)
            raise AuthError(f"Failed to send code: {e}") from e

    async def sign_in_with_code(self, code: str) -> Dict[str, Any]:
        """Sign in using the received SMS or Telegram app code.

        Returns user dict on success, or raises SessionPasswordNeededError if 2FA enabled.
        """
        if not self.phone_number or not self.phone_code_hash:
            raise AuthError("No pending login request. Please enter your phone number first.")

        clean_code = code.strip().replace(" ", "").replace("-", "")
        client = self.manager.client

        try:
            user = await client.sign_in(
                phone=self.phone_number,
                code=clean_code,
                phone_code_hash=self.phone_code_hash,
            )
            self.current_user = {
                "id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
                "phone": user.phone or self.phone_number,
            }
            self.state = AuthState.AUTHORIZED
            logger.info("Successfully signed in with code as %s", self.current_user["first_name"])
            return self.current_user

        except SessionPasswordNeededError:
            self.state = AuthState.WAITING_FOR_PASSWORD
            logger.info("2FA password required to complete authentication.")
            raise

        except PhoneCodeInvalidError as e:
            raise AuthError("The verification code entered is invalid.") from e
        except PhoneCodeExpiredError as e:
            raise AuthError("The verification code has expired. Please request a new one.") from e
        except FloodWaitError as e:
            raise AuthError(f"Too many attempts. Please wait {e.seconds} seconds.") from e
        except Exception as e:
            logger.error("Sign-in with code error: %s", e)
            raise AuthError(f"Authentication failed: {e}") from e

    async def sign_in_with_password(self, password: str) -> Dict[str, Any]:
        """Complete 2FA login using cloud password.

        The password is used transiently in-memory and never written to disk or logged.
        """
        client = self.manager.client
        try:
            # Telethon computes SRP hash client-side; plaintext password is never stored
            user = await client.sign_in(password=password)
            self.current_user = {
                "id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
                "phone": user.phone or self.phone_number,
            }
            self.state = AuthState.AUTHORIZED
            logger.info("Successfully signed in with 2FA password as %s", self.current_user["first_name"])
            return self.current_user
        except PasswordHashInvalidError as e:
            raise AuthError("Invalid 2FA password. Please check your cloud password.") from e
        except FloodWaitError as e:
            raise AuthError(f"Too many attempts. Please wait {e.seconds} seconds.") from e
        except Exception as e:
            logger.error("Sign-in with password error: %s", e)
            raise AuthError(f"2FA authentication failed: {e}") from e
        finally:
            # Explicitly overwrite password reference from local scope
            password = None

    async def log_out(self) -> bool:
        """Terminate the session on Telegram servers and delete local session files."""
        client = self.manager.client
        if client and client.is_connected():
            try:
                logger.info("Logging out from Telegram...")
                await client.log_out()
            except Exception as e:
                logger.warning("Error during remote log_out: %s", e)

        # Clear session files locally
        session_file = self.manager.session_file_path
        if session_file.exists():
            try:
                session_file.unlink()
                logger.info("Deleted local session file %s", session_file)
            except Exception as e:
                logger.warning("Failed deleting session file: %s", e)

        journal_file = session_file.with_name(f"{session_file.name}-journal")
        if journal_file.exists():
            try:
                journal_file.unlink()
            except Exception:
                pass

        self.state = AuthState.UNAUTHORIZED
        self.phone_number = None
        self.phone_code_hash = None
        self.current_user = None
        return True
