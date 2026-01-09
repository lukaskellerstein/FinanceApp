"""
Centralized thread management for the application.

Provides:
- Named thread registration
- Thread pool for background tasks
- Graceful shutdown coordination
"""

from __future__ import annotations
import logging
import threading
from typing import Dict, Optional, Callable, Any, List
from concurrent.futures import ThreadPoolExecutor, Future
from enum import Enum

log = logging.getLogger("CellarLogger")


class ManagedThread:
    """
    Wrapper for managed threads with lifecycle tracking.

    Provides a clean interface for starting, stopping, and monitoring threads.
    """

    def __init__(
        self,
        name: str,
        target: Callable[[], None],
        daemon: bool = True,
    ):
        """
        Initialize a managed thread.

        Args:
            name: Unique name for the thread
            target: Function to run in the thread
            daemon: If True, thread will be killed when main thread exits
        """
        self.name = name
        self.target = target
        self.daemon = daemon
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._error: Optional[Exception] = None

    def start(self) -> None:
        """Start the thread."""
        if self._running:
            log.warning(f"Thread {self.name} is already running")
            return

        self._running = True
        self._error = None
        self._thread = threading.Thread(
            name=self.name,
            target=self._run_wrapper,
            daemon=self.daemon,
        )
        self._thread.start()
        log.info(f"Thread {self.name} started")

    def _run_wrapper(self) -> None:
        """Wrapper that catches exceptions and tracks state."""
        try:
            self.target()
        except Exception as e:
            log.error(f"Thread {self.name} failed with error: {e}")
            self._error = e
        finally:
            self._running = False
            log.info(f"Thread {self.name} stopped")

    def stop(self) -> None:
        """Signal the thread to stop (thread must check this flag)."""
        self._running = False

    def join(self, timeout: Optional[float] = None) -> None:
        """Wait for the thread to complete."""
        if self._thread is not None:
            self._thread.join(timeout)

    @property
    def is_alive(self) -> bool:
        """Check if thread is currently running."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_running(self) -> bool:
        """Check if thread is in running state (may be finishing)."""
        return self._running

    @property
    def error(self) -> Optional[Exception]:
        """Get any error that occurred in the thread."""
        return self._error


class ThreadManager:
    """
    Centralized thread management for the application.

    Provides:
    - Named thread registration and tracking
    - Thread pool for short-lived background tasks
    - Graceful shutdown coordination
    - Thread status monitoring
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize the thread manager.

        Args:
            max_workers: Maximum number of threads in the pool
        """
        self._threads: Dict[str, ManagedThread] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="TaskPool",
        )
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._shutdown = False

        log.info(f"ThreadManager initialized with {max_workers} workers")

    def register_thread(
        self,
        name: str,
        target: Callable[[], None],
        daemon: bool = True,
        auto_start: bool = False,
    ) -> ManagedThread:
        """
        Register a named thread.

        Args:
            name: Unique name for the thread
            target: Function to run in the thread
            daemon: If True, thread will be killed when main thread exits
            auto_start: If True, start the thread immediately

        Returns:
            The managed thread object

        Raises:
            ValueError: If a thread with this name already exists
        """
        with self._lock:
            if name in self._threads:
                existing = self._threads[name]
                if existing.is_alive:
                    raise ValueError(f"Thread {name} already registered and running")
                # Remove dead thread
                del self._threads[name]

            thread = ManagedThread(name, target, daemon)
            self._threads[name] = thread

            if auto_start:
                thread.start()

            return thread

    def get_thread(self, name: str) -> Optional[ManagedThread]:
        """
        Get a registered thread by name.

        Args:
            name: Thread name

        Returns:
            The managed thread or None if not found
        """
        return self._threads.get(name)

    def start_thread(self, name: str) -> bool:
        """
        Start a registered thread.

        Args:
            name: Thread name

        Returns:
            True if started, False if not found or already running
        """
        thread = self._threads.get(name)
        if thread is None:
            return False

        if not thread.is_alive:
            thread.start()
            return True

        return False

    def stop_thread(self, name: str) -> bool:
        """
        Signal a thread to stop.

        Args:
            name: Thread name

        Returns:
            True if signal sent, False if not found
        """
        thread = self._threads.get(name)
        if thread is None:
            return False

        thread.stop()
        return True

    def submit_task(
        self,
        task_id: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        """
        Submit a task to the thread pool.

        Args:
            task_id: Unique ID for the task
            fn: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Future object for the task
        """
        with self._lock:
            # Cancel existing task with same ID
            if task_id in self._futures:
                self._futures[task_id].cancel()

            future = self._executor.submit(fn, *args, **kwargs)
            self._futures[task_id] = future

            # Add callback to clean up
            def cleanup(f: Future) -> None:
                with self._lock:
                    if self._futures.get(task_id) is f:
                        del self._futures[task_id]

            future.add_done_callback(cleanup)

            return future

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if not found or already running
        """
        with self._lock:
            future = self._futures.get(task_id)
            if future:
                return future.cancel()
            return False

    def get_active_threads(self) -> Dict[str, bool]:
        """
        Get status of all managed threads.

        Returns:
            Dictionary mapping thread name to alive status
        """
        return {name: thread.is_alive for name, thread in self._threads.items()}

    def get_active_tasks(self) -> List[str]:
        """
        Get IDs of active tasks.

        Returns:
            List of task IDs that are still running
        """
        with self._lock:
            return [
                task_id
                for task_id, future in self._futures.items()
                if not future.done()
            ]

    def shutdown(self, wait: bool = True, timeout: Optional[float] = 5.0) -> None:
        """
        Shutdown all threads and the executor.

        Args:
            wait: If True, wait for threads to finish
            timeout: Timeout in seconds for waiting (per thread)
        """
        if self._shutdown:
            return

        self._shutdown = True
        log.info("ThreadManager shutting down...")

        # Stop all managed threads
        for name, thread in self._threads.items():
            log.info(f"Stopping thread: {name}")
            thread.stop()

        # Wait for threads if requested
        if wait:
            for name, thread in self._threads.items():
                if thread.is_alive:
                    log.info(f"Waiting for thread: {name}")
                    thread.join(timeout)
                    if thread.is_alive:
                        log.warning(f"Thread {name} did not stop in time")

        # Shutdown thread pool
        self._executor.shutdown(wait=wait)

        log.info("ThreadManager shutdown complete")

    @property
    def is_shutdown(self) -> bool:
        """Check if manager has been shut down."""
        return self._shutdown
