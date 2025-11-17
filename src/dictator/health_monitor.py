"""Health monitoring and crash recovery for Dictator app.

Monitors critical components and restarts them if they fail.
Especially important after system sleep/wake cycles.
"""

import threading
import time
import logging
from typing import Callable, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ComponentHealth:
    """Track health state of a component."""

    def __init__(self, name: str):
        self.name = name
        self.last_check = datetime.now()
        self.is_healthy = True
        self.failure_count = 0
        self.last_failure = None

    def mark_healthy(self):
        """Mark component as healthy."""
        self.last_check = datetime.now()
        self.is_healthy = True
        self.failure_count = 0

    def mark_failed(self, error: Optional[Exception] = None):
        """Mark component as failed."""
        self.last_check = datetime.now()
        self.is_healthy = False
        self.failure_count += 1
        self.last_failure = datetime.now()
        if error:
            logger.error(f"{self.name} marked as failed: {error}")

    def needs_check(self, check_interval: float = 5.0) -> bool:
        """Check if component needs health check."""
        return (datetime.now() - self.last_check).total_seconds() > check_interval


class HealthMonitor:
    """Monitor and recover critical app components."""

    def __init__(self):
        """Initialize health monitor."""
        self.components: Dict[str, ComponentHealth] = {}
        self.recovery_callbacks: Dict[str, Callable] = {}
        self.check_callbacks: Dict[str, Callable] = {}
        self._monitoring = False
        self._monitor_thread = None
        self._last_sleep_check = datetime.now()
        self._system_was_sleeping = False

    def register_component(
        self,
        name: str,
        check_callback: Callable[[], bool],
        recovery_callback: Callable[[], None],
    ):
        """Register a component for health monitoring.

        Args:
            name: Component name
            check_callback: Function that returns True if healthy
            recovery_callback: Function to call to recover component
        """
        self.components[name] = ComponentHealth(name)
        self.check_callbacks[name] = check_callback
        self.recovery_callbacks[name] = recovery_callback
        logger.info(f"Registered component for monitoring: {name}")

    def start_monitoring(self, check_interval: float = 5.0):
        """Start monitoring all registered components.

        Args:
            check_interval: Seconds between health checks
        """
        if self._monitoring:
            logger.warning("Health monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(check_interval,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info(f"Started health monitoring (interval: {check_interval}s)")

    def stop_monitoring(self):
        """Stop health monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Stopped health monitoring")

    def _monitor_loop(self, check_interval: float):
        """Main monitoring loop.

        Args:
            check_interval: Seconds between checks
        """
        while self._monitoring:
            try:
                # Check if system went to sleep
                if self._detect_sleep():
                    logger.warning("System wake from sleep detected - checking all components")
                    self._handle_wake_from_sleep()

                # Check each component
                for name, health in self.components.items():
                    if health.needs_check(check_interval):
                        self._check_component(name)

                time.sleep(1.0)  # Short sleep for responsive shutdown

            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                time.sleep(check_interval)

    def _detect_sleep(self) -> bool:
        """Detect if system went to sleep.

        Returns:
            True if sleep was detected
        """
        now = datetime.now()
        time_diff = (now - self._last_sleep_check).total_seconds()

        # If more than 30 seconds passed since last check, system likely slept
        was_sleeping = time_diff > 30

        self._last_sleep_check = now

        if was_sleeping and not self._system_was_sleeping:
            self._system_was_sleeping = True
            return True

        if not was_sleeping:
            self._system_was_sleeping = False

        return False

    def _handle_wake_from_sleep(self):
        """Handle system wake from sleep - restart all components."""
        logger.info("Handling wake from sleep - restarting all components")

        for name in self.components:
            try:
                # Force recovery of all components after sleep
                logger.info(f"Restarting {name} after sleep")
                self.recovery_callbacks[name]()
                self.components[name].mark_healthy()
            except Exception as e:
                logger.error(f"Failed to restart {name} after sleep: {e}")
                self.components[name].mark_failed(e)

    def _check_component(self, name: str):
        """Check health of a single component.

        Args:
            name: Component name
        """
        health = self.components[name]
        check_callback = self.check_callbacks[name]

        try:
            is_healthy = check_callback()

            if is_healthy:
                if not health.is_healthy:
                    logger.info(f"{name} recovered")
                health.mark_healthy()
            else:
                raise Exception(f"{name} health check returned False")

        except Exception as e:
            health.mark_failed(e)

            # Try recovery if component failed
            if health.failure_count <= 3:  # Max 3 recovery attempts
                logger.warning(f"Attempting to recover {name} (attempt {health.failure_count})")
                try:
                    self.recovery_callbacks[name]()
                    # Will check health on next iteration
                except Exception as recovery_error:
                    logger.error(f"Recovery failed for {name}: {recovery_error}")
            else:
                logger.error(f"{name} failed too many times, giving up")

    def get_status(self) -> Dict[str, dict]:
        """Get current health status of all components.

        Returns:
            Dictionary with component health info
        """
        status = {}
        for name, health in self.components.items():
            status[name] = {
                "healthy": health.is_healthy,
                "last_check": health.last_check.isoformat(),
                "failure_count": health.failure_count,
                "last_failure": health.last_failure.isoformat() if health.last_failure else None,
            }
        return status