import asyncio
import signal
import sys
import yaml

from utils.config import Config, ConfigError
from utils.logger import logger
from utils.args_parser import parse_arguments
from utils.signal_handlers import SignalHandlers
from core.service_handler import ServiceHandler
from core.service_monitor import ServiceMonitor
from core.shell import ControlShell

async def main():
    """Main Taskmaster entry point."""
    
    # Parse command-line arguments
    try:
        config_path, log_level = parse_arguments()
    except SystemExit:
        return
    
    # Set log level if specified
    if log_level:
        logger.setLevel(log_level)
        logger.info(f"Log level set to {log_level}")
    
    # Load and validate configuration
    try:
        config = Config(config_path)
        logger.info(f"Configuration loaded successfully from: {config_path}")
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", config_path)
        print(f"\nError: Configuration file not found: {config_path}", file=sys.stderr)
        print("Please provide a valid configuration file with -f option", file=sys.stderr)
        return
    except ConfigError as e:
        print(f"\nConfiguration Error: {e}", file=sys.stderr)
        return
    except yaml.YAMLError as e:
        logger.error("YAML parsing error: %s", e)
        print(f"\nYAML Error: Invalid YAML syntax in configuration file", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        return
    except Exception as e:
        logger.error("Fatal error loading configuration: %s", e)
        print(f"\nFatal error: {e}", file=sys.stderr)
        return

    # Initialize services and monitoring components
    try:
        handler = ServiceHandler(config.services, email=config.email, config_path=config_path)
        signal_handlers.handler_ref = handler
        monitor = ServiceMonitor(handler)
        
        logger.info("Taskmaster initialized successfully")
        
        # Start autostart services
        logger.info("Starting autostart services...")
        await handler.autostart()
        
        # Launch service monitoring loop
        logger.info("Starting service monitor...")
        await monitor.start()
        
        # Launch control shell
        logger.info("Launching control shell...")
        shell = ControlShell(handler, monitor)
        await shell.run()
        
    except Exception as e:
        logger.error("Fatal error during initialization: %s", e)
        print(f"\nFatal error: {e}", file=sys.stderr)
        return


async def main_with_signal():
    """Run main() and handle clean cancellation + reload."""
    try:
        main_task = asyncio.create_task(main())
        await signal_handlers.run_with_signals(main_task)
        logger.info("All tasks completed successfully.")
        
    except asyncio.CancelledError:
        logger.info("Main task was cancelled.")
    except Exception as e:
        logger.error("Fatal error in main: %s", e)
        print(f"Fatal error: {e}", file=sys.stderr)
    finally:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Taskmaster event loop cleanup complete.")


if __name__ == "__main__":
    signal_handlers = SignalHandlers()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handlers.handle_sigint)
    signal.signal(signal.SIGHUP, signal_handlers.handle_sighup)
    
    logger.info("Signal handlers registered (SIGINT, SIGHUP)")
    
    try:
        logger.info("Starting Taskmaster...")
        asyncio.run(main_with_signal())
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
        logger.info("Interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        logger.error("Fatal error outside asyncio: %s", e)
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)