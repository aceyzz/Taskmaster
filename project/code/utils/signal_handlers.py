import asyncio
import contextlib
from utils.logger import logger
from utils.config import Config, ConfigError


class SignalHandlers:
    """Handles SIGINT and SIGHUP signals for Taskmaster."""
    
    def __init__(self):
        self.stop_event = asyncio.Event()
        self.reload_event = asyncio.Event()
        self.handler_ref = None
        self.shutdown_in_progress = False
    
    def handle_sigint(self, sig, frame):
        """Handle SIGINT cleanly (Ctrl+C)."""
        if self.shutdown_in_progress:
            return
        self.shutdown_in_progress = True
        print("\nReceived SIGINT (Ctrl+C), shutting down gracefully...")
        logger.info("Received SIGINT, initiating graceful shutdown")
        self.stop_event.set()
    
    def handle_sighup(self, sig, frame):
        """Handle SIGHUP to trigger configuration reload."""
        print("\nReceived SIGHUP: reloading configuration...")
        logger.info("Received SIGHUP, triggering configuration reload")
        self.reload_event.set()
    
    async def handle_stop_signal(self):
        """Handle graceful shutdown when stop signal is received."""
        logger.info("Received stop signal, shutting down...")
        print("\nShutting down all services...")
        
        if self.handler_ref:
            try:
                await self.handler_ref.delete()
            except Exception as e:
                logger.error("Error stopping services: %s", e)
        
        logger.info("Taskmaster shutdown complete")
        print("Taskmaster stopped.")
        
        # Force exit after shutdown
        import sys
        sys.exit(0)
    
    async def handle_reload_signal(self):
        """Handle configuration reload when SIGHUP is received."""
        self.reload_event.clear()
        
        if self.handler_ref is None:
            logger.warning("Received SIGHUP before handler initialization.")
            print("Warning: Cannot reload - handler not initialized yet.")
            return
        
        print("Reloading configuration (via SIGHUP)...")
        try:
            changed = await self.handler_ref.reload(self.handler_ref.config_path)
            if changed:
                logger.info("Configuration reloaded successfully (SIGHUP).")
                print("Configuration reloaded successfully.")
            else:
                logger.info("No configuration changes detected (SIGHUP).")
                print("No configuration changes detected.")
        except FileNotFoundError as e:
            error_msg = f"Configuration file not found during reload: {e}"
            logger.error(error_msg)
            print(f"Error: {error_msg}", file=sys.stderr)
        except ConfigError as e:
            error_msg = f"Configuration error during reload: {e}"
            logger.error(error_msg)
            print(f"Error: {error_msg}", file=sys.stderr)
        except Exception as e:
            error_msg = f"Unexpected error during SIGHUP reload: {e}"
            logger.error(error_msg)
            print(f"Error: {error_msg}", file=sys.stderr)
    
    async def run_with_signals(self, main_task):
        """Run main task while handling signals."""
        stop_task = asyncio.create_task(self.stop_event.wait())
        reload_task = asyncio.create_task(self.reload_event.wait())
        
        while True:
            done, pending = await asyncio.wait(
                [main_task, stop_task, reload_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            if stop_task in done:
                await self.handle_stop_signal()
                
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                
                return
            
            if reload_task in done:
                await self.handle_reload_signal()
                reload_task = asyncio.create_task(self.reload_event.wait())
            
            if main_task in done:
                logger.info("Main task completed.")
                
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                
                return
        
        logger.info("All tasks completed successfully.")