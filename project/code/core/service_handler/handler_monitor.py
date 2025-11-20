import asyncio
from utils.logger import logger


class MonitorMixin:
    """Background monitoring loop for detecting crashes and handling autorestart logic."""

    async def monitor(self):
        """Main monitoring loop that checks service health and handles restarts."""
        logger.info("Monitor loop started.")
        while True:
            try:
                async with self._lock:
                    for name, instances in self.services.items():
                        cfg = self.service_configs[name]
                        mode = cfg.get("autorestart", "never")
                        exitcodes = cfg.get("exitcodes", [0])
                        max_retries = cfg.get("startretries", 0)

                        for i, inst in enumerate(instances):
                            await self._check_instance(name, i, inst, mode, exitcodes, max_retries)

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("Monitor loop cancelled.")
                break

            except Exception as e:
                logger.error("Error in monitor loop: %s", e)
                await asyncio.sleep(1)

    async def _check_instance(self, name, i, inst, mode, exitcodes, max_retries):
        """Check a single service instance and handle its state."""
        proc = inst.process
        if not proc:
            return

        # Process still running - nothing to do
        if proc.poll() is None:
            return

        # Skip processes already in terminal state to avoid log spam
        if getattr(inst, "state", None) in ("stopped", "backoff"):
            return

        code = proc.returncode
        expected = code in exitcodes
        should_restart = mode == "always" or (mode == "unexpected" and not expected)

        # Case 1: Service never reached running state
        if not getattr(inst, "ever_running", False):
            await self._handle_early_exit(name, i, inst, code, expected, should_restart, max_retries)
        # Case 2: Service was running normally
        elif expected:
            await self._handle_expected_exit(name, i, inst, code, should_restart, max_retries)
        # Case 3: Unexpected crash
        else:
            await self._handle_unexpected_crash(name, i, inst, code, should_restart, max_retries, mode)

    async def _handle_early_exit(self, name, i, inst, code, expected, should_restart, max_retries):
        """Handle services that exit during startup phase."""
        if expected:
            logger.info(
                "Service '%s' instance %d exited early with expected code %s - no restart needed.",
                name, i, code,
            )
            inst.state = "stopped"
            return

        # Premature crash during starttime
        inst._restart_attempts = getattr(inst, "_restart_attempts", 0) + 1
        if inst._restart_attempts > max_retries:
            logger.error(
                "Service '%s' instance %d failed to start properly %d times - giving up.",
                name, i, inst._restart_attempts,
            )
            inst.state = "backoff"
            return

        if should_restart:
            logger.warning(
                "Service '%s' instance %d crashed early (code=%s). Restarting attempt %d/%d...",
                name, i, code, inst._restart_attempts, max_retries,
            )
            await asyncio.sleep(1.0)
            try:
                await inst.start()
            except Exception as e:
                logger.error("Failed to restart '%s' instance %d: %s", name, i, e)

    async def _handle_expected_exit(self, name, i, inst, code, should_restart, max_retries):
        """Handle services that exit with expected exit codes."""
        if should_restart:
            # autorestart=always - restart even with expected code
            inst._restart_attempts = getattr(inst, "_restart_attempts", 0)
            if inst._restart_attempts < max_retries:
                inst._restart_attempts += 1
                logger.info(
                    "Service '%s' instance %d exited normally (code=%s). Restarting (autorestart=always) attempt %d/%d...",
                    name, i, code, inst._restart_attempts, max_retries,
                )
                await asyncio.sleep(0.3)
                try:
                    await inst.start()
                except Exception as e:
                    logger.error("Failed to restart '%s' instance %d: %s", name, i, e)
            else:
                logger.error(
                    "Service '%s' instance %d exceeded restart limit (%d attempts).",
                    name, i, max_retries,
                )
                inst.state = "backoff"
        else:
            # Normal exit, no restart
            logger.info("Service '%s' instance %d exited normally (code=%s).", name, i, code)
            inst.state = "stopped"

    async def _handle_unexpected_crash(self, name, i, inst, code, should_restart, max_retries, mode):
        """Handle services that crash unexpectedly."""
        inst._restart_attempts = getattr(inst, "_restart_attempts", 0)
        if should_restart:
            if inst._restart_attempts < max_retries:
                inst._restart_attempts += 1
                logger.warning(
                    "Service '%s' instance %d died unexpectedly (code=%s). Restarting attempt %d/%d...",
                    name, i, code, inst._restart_attempts, max_retries,
                )
                await asyncio.sleep(0.3)
                try:
                    await inst.start()
                except Exception as e:
                    logger.error("Failed to restart '%s' instance %d: %s", name, i, e)
            else:
                logger.error(
                    "Service '%s' instance %d exceeded restart limit (%d attempts).",
                    name, i, max_retries,
                )
                inst.state = "backoff"
        else:
            logger.info(
                "Service '%s' instance %d stopped (code=%s). No restart (mode=%s).",
                name, i, code, mode,
            )
            inst.state = "stopped"