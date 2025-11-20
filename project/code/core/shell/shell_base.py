import asyncio
import readline
from utils.logger import logger
from .shell_commands import ShellCommands


class ControlShell:
    """
    Interactive control shell for Taskmaster.
    Provides a non-blocking command interface to manage services.
    """

    def __init__(self, handler, monitor):
        self.handler = handler
        self.monitor = monitor
        self._running = True
        self._prompt = "> "
        self.commands = ShellCommands(handler, monitor, self)
        
        # Configure readline for better UX
        self._setup_readline()
    
    def _setup_readline(self):
        """Configure readline for line editing, history, and completion."""
        # Enable history (arrow up/down)
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self._completer)
        readline.set_completer_delims(' \t\n')  # Important pour la completion
        
        # Set history file
        import os
        history_file = os.path.expanduser('~/.taskmaster_history')
        try:
            readline.read_history_file(history_file)
        except FileNotFoundError:
            pass
        
        # Save history on exit
        import atexit
        atexit.register(readline.write_history_file, history_file)
    
    def _completer(self, text, state):
        """Auto-completion for commands and service names."""
        # Available commands
        commands = ['status', 'start', 'stop', 'restart', 'reload', 'exit', 'quit', 'help']
        
        # Add service names for start/stop/restart commands
        service_names = list(self.handler.services.keys()) + ['all']
        
        # Combine all options
        options = commands + service_names
        
        # Filter options that match the current text
        matches = [opt for opt in options if opt.startswith(text)]
        
        # Return the state-th match
        if state < len(matches):
            return matches[state]
        return None

    async def run(self):
        """Run the interactive shell loop."""
        logger.info("[Shell] Control shell started.")
        print("Welcome to Taskmaster shell. Type 'help' for commands.\n")

        try:
            while self._running:
                try:
                    # Use input() directly in a thread to preserve readline functionality
                    command = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input(self._prompt)
                    )
                    command = command.strip()
                    if not command:
                        continue
                    await self.handle_command(command)
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting Taskmaster shell...")
                    await self.commands.cmd_exit()
                except Exception as e:
                    logger.error("[Shell] Unexpected error: %s", e)
                    print(f"Error: {e}")
        except asyncio.CancelledError:
            logger.info("[Shell] Shell task cancelled, exiting gracefully.")
            self._running = False

    async def handle_command(self, command: str):
        """Dispatch user input to the corresponding shell command."""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]

        mapping = {
            "status": self.commands.cmd_status,
            "start": self.commands.cmd_start,
            "stop": self.commands.cmd_stop,
            "restart": self.commands.cmd_restart,
            "reload": self.commands.cmd_reload,
            "exit": self.commands.cmd_exit,
            "quit": self.commands.cmd_exit,
            "help": self.commands.cmd_help,
        }

        if cmd in mapping:
            await mapping[cmd](args)
        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' to see available commands.")
            logger.warning("[Shell] Unknown command: %s", cmd)