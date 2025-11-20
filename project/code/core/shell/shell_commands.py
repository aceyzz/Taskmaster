import asyncio
from utils.logger import logger


class ShellCommands:
    """
    Group of Taskmaster shell commands.
    Each command interacts with the service handler and monitor.
    """

    def __init__(self, handler, monitor, shell):
        self.handler = handler
        self.monitor = monitor
        self.shell = shell

    async def cmd_status(self, args=None):
        """Display current status of all services."""
        report = self.handler.status()
        print("Service status:")
        for name, data in report.items():
            states = ", ".join(data["states"])
            print(f" - [{name}] -> {states} (instances: {data['numprocs']})")
        logger.info("[Shell] Status command executed.")

    async def cmd_start(self, args):
        """Start a specific service or all services."""
        await self._execute_service_action(args, "start", self.handler.start)

    async def cmd_stop(self, args):
        """Stop a specific service or all services."""
        await self._execute_service_action(args, "stop", self.handler.stop)

    async def cmd_restart(self, args):
        """Restart a specific service or all services."""
        await self._execute_service_action(args, "restart", self.handler.restart)

    async def _execute_service_action(self, args, action_name, action_func):
        """Execute a service action (start/stop/restart) on target service(s)."""
        if not args:
            print(f"Usage: {action_name} <service>|all")
            return
        
        target = args[0]
        
        # Proper gerund form for logging
        action_gerund = {
            "start": "Starting",
            "stop": "Stopping", 
            "restart": "Restarting"
        }.get(action_name, action_name.capitalize() + "ing")
        
        if target == "all":
            logger.info("[Shell] %s all services.", action_gerund)
            for name in self.handler.services.keys():
                await action_func(name)
            print(f"{action_name.capitalize()} command executed for all services.")
        else:
            if target not in self.handler.services:
                print(f"Service '{target}' not found.")
                logger.error("[Shell] Tried to %s unknown service: %s", action_name, target)
                return
            logger.info("[Shell] %s service '%s'.", action_gerund, target)
            result = await action_func(target)
            
            # Display appropriate message based on result
            if action_name == "start":
                if result:
                    print(f"Service '{target}' started successfully.")
                else:
                    print(f"Service '{target}' could not be started (already running or failed).")
            elif action_name == "stop":
                if result:
                    print(f"Service '{target}' stopped successfully.")
                else:
                    print(f"Service '{target}' is not running.")
            else:  # restart
                print(f"Service '{target}' restarted.")

    async def cmd_reload(self, args=None):
        """Reload configuration (SIGHUP equivalent)."""
        logger.info("[Shell] Reload command received.")
        print("Reloading configuration...")

        async def _do_reload():
            changed = await self.handler.reload(self.handler.config_path)
            if changed:
                await self.monitor.reload()
            logger.info("[Shell] Reload completed.")

        asyncio.create_task(_do_reload())
        print("Configuration reload in progress (non-blocking)...")

    async def cmd_help(self, args=None):
        """Display list of available commands."""
        print(
            "\nAvailable commands:\n"
            " - status\n"
            " - start <service>|all\n"
            " - stop <service>|all\n"
            " - restart <service>|all\n"
            " - reload\n"
            " - exit | quit\n"
            " - help\n"
        )

    async def cmd_exit(self, args=None):
        """Exit Taskmaster shell and stop all services cleanly."""
        logger.info("[Shell] Exit command received.")
        print("Stopping all services and shutting down...")

        try:
            if hasattr(self.monitor, "stop"):
                await asyncio.wait_for(self.monitor.stop(), timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning("[Shell] Monitor stop timed out, continuing shutdown.")

        try:
            if hasattr(self.handler, "delete"):
                await asyncio.wait_for(self.handler.delete(), timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning("[Shell] Timeout while stopping services: forcing clean exit as per spec.")

        self.shell._running = False
        logger.info("[Shell] Taskmaster exited cleanly.")
        print("Shutdown complete.")