import asyncio
from utils.logger import logger
from core.service_handler import ServiceHandler


class ServiceMonitor:
    def __init__(self, handler: ServiceHandler):
        self.handler = handler
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the monitoring task."""
        if self._task and not self._task.done():
            logger.warning("Monitor task already running.")
            return
        logger.info("Starting service monitor task.")
        self._task = asyncio.create_task(self.handler.monitor())

    async def stop(self):
        """Cancel the monitoring task if running."""
        if self._task and not self._task.done():
            logger.info("Stopping service monitor task...")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Monitor task stopped cleanly.")

    async def reload(self):
        """Reload the monitor task after config changes."""
        logger.info("Reloading monitor to reflect new configuration...")
        await self.stop()
        await self.start()