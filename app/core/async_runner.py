"""Thread-safe asyncio event loop runner for PySide6 integration."""

import asyncio
import threading
from typing import Any, Coroutine, Optional
from PySide6.QtCore import QObject, Signal

from .logger import get_logger

logger = get_logger("core.async_runner")


class AsyncRunner(QObject):
    """Manages a background thread running an asyncio event loop for Telethon.

    Guarantees thread-safe dispatching of callbacks onto Qt main GUI thread.
    """

    _dispatch_signal = Signal(object, object)

    def __init__(self):
        super().__init__()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._dispatch_signal.connect(self._on_dispatch)
        self._start_loop_thread()

    def _on_dispatch(self, func, arg):
        """Execute callback function on the Qt GUI thread."""
        try:
            func(arg)
        except Exception as e:
            logger.error("Exception in GUI thread callback: %s", e, exc_info=True)

    def _dispatch(self, func, arg):
        """Dispatch callback to Qt main thread if application is running, else execute directly."""
        from PySide6.QtWidgets import QApplication

        qapp = QApplication.instance()
        if qapp is not None and threading.current_thread() is not threading.main_thread():
            self._dispatch_signal.emit(func, arg)
        else:
            try:
                func(arg)
            except Exception as e:
                logger.error("Exception executing callback directly: %s", e, exc_info=True)

    def _start_loop_thread(self) -> None:
        """Start background daemon thread with dedicated asyncio loop."""
        self._loop = asyncio.new_event_loop()
        self._is_running = True

        def run_loop():
            asyncio.set_event_loop(self._loop)
            logger.debug("Background asyncio event loop started.")
            self._loop.run_forever()
            logger.debug("Background asyncio event loop terminated.")

        self._thread = threading.Thread(target=run_loop, name="AsyncioWorkerThread", daemon=True)
        self._thread.start()

    def run_coroutine(self, coro: Coroutine) -> Any:
        """Submit a coroutine to the background loop and wait synchronously for result."""
        if not self._loop or not self._is_running:
            raise RuntimeError("Async event loop is not running.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def run_coroutine_async(self, coro: Coroutine, callback=None, error_callback=None):
        """Submit a coroutine to the background loop asynchronously with thread-safe callbacks."""
        if not self._loop or not self._is_running:
            raise RuntimeError("Async event loop is not running.")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)

        def done_handler(fut):
            try:
                res = fut.result()
                if callback:
                    self._dispatch(callback, res)
            except Exception as exc:
                logger.error("Error in background coroutine: %s", exc)
                if error_callback:
                    self._dispatch(error_callback, exc)

        future.add_done_callback(done_handler)
        return future

    def stop(self) -> None:
        """Stop background event loop and join thread."""
        if self._loop and self._is_running:
            self._is_running = False
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=2.0)
            logger.info("AsyncRunner stopped.")


# Singleton instance for application
async_runner = AsyncRunner()
