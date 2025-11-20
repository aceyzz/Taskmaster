import asyncio
from utils.logger import logger


class LifecycleMixin:
    """Mixin for managing service start, stop, restart, and status."""

    async def autostart(self):
        """Start all services with autostart=True."""
        for name, cfg in self.service_configs.items():
            if cfg.get("autostart", False):
                logger.info("[Autostart] Launching service '%s'...", name)
                await self.start(name)
            else:
                logger.debug("[Autostart] Skipping service '%s' (autostart=false).", name)

    async def _start_nolock(self, name: str):
        """Start all instances of a service without lock (internal use). Returns True if at least one instance started."""
        if name not in self.services:
            logger.error("Service '%s' not found.", name)
            return False

        cfg = self.service_configs.get(name, {})
        retries = cfg.get("startretries", 0)
        any_started = False

        for i, inst in enumerate(self.services[name]):
            if inst.process and inst.process.poll() is None:
                logger.warning("Service '%s' instance %d already running.", name, i)
                continue

            attempt = 0
            while attempt <= retries:
                attempt += 1
                try:
                    logger.info("Starting '%s' instance %d (attempt %d).", name, i, attempt)
                    result = await inst.start()

                    if result and inst.process and inst.process.poll() is None:
                        logger.info("Service '%s' instance %d started successfully.", name, i)
                        if hasattr(inst, "_restart_attempts"):
                            inst._restart_attempts = 0
                        any_started = True
                        break
                    raise RuntimeError("Exited early")
                except Exception as e:
                    logger.error("Failed to start '%s' instance %d: %s", name, i, e)
                    if attempt > retries:
                        logger.error(
                            "Giving up on '%s' instance %d after %d attempts.", name, i, retries
                        )
                    else:
                        await asyncio.sleep(1)
        
        return any_started

    async def start(self, name: str):
        """Public start: acquire lock then start service."""
        async with self._lock:
            return await self._start_nolock(name)

    async def _stop_nolock(self, name: str):
        """Stop service instances without lock (internal use). Returns True if at least one instance stopped."""
        if name not in self.services:
            logger.error("Service '%s' not found.", name)
            return False

        any_stopped = False
        for i, inst in enumerate(self.services[name]):
            try:
                logger.info("Stopping '%s' instance %d...", name, i)
                result = await inst.stop()
                if result:
                    any_stopped = True
            except Exception as e:
                logger.error("Error stopping '%s' instance %d: %s", name, i, e)
        
        return any_stopped

    async def stop(self, name: str):
        """Public stop: acquire lock then stop service."""
        async with self._lock:
            return await self._stop_nolock(name)

    async def restart(self, name: str):
        """Restart a service cleanly."""
        logger.info("Restarting service '%s'...", name)
        await self.stop(name)
        await asyncio.sleep(1)
        await self.start(name)
        logger.info("Service '%s' restarted successfully.", name)

    def status(self):
        """Return a snapshot of all services' states."""
        report = {}
        for name, instances in self.services.items():
            states = ["Running" if (inst.process and inst.process.poll() is None) else "Stopped"
                      for inst in instances]
            report[name] = {"numprocs": len(instances), "states": states}
        return report

    async def delete(self):
        """Stop and clear all services."""
        logger.info("Deleting all services...")
        async with self._lock:
            for name in list(self.services.keys()):
                await self._stop_nolock(name)
                await asyncio.sleep(0.2)
            self.services.clear()
            self.service_configs.clear()
        logger.info("All services stopped and cleared.")