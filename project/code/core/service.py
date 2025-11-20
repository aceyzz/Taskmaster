import getpass
import os
import shlex
import asyncio
import signal
import subprocess

from utils.logger import logger
from utils.signals import get_signal
from core.process_utils import open_streams, validate_user


class Service:
    def __init__(self, config):
        self.name = config["name"]
        self.cmd = config["cmd"]
        self.cwd = config.get("workingdir", os.getcwd())
        # Convert umask to integer if it's a string
        umask_value = config.get("umask", 0o22)
        if isinstance(umask_value, str):
            self.umask = int(umask_value, 8)  # Parse as octal
        else:
            self.umask = int(umask_value)
        self.env = {**os.environ, **config.get("env", {})}
        self.stdout_path = config.get("stdout")
        self.stderr_path = config.get("stderr")
        self.autostart = config.get("autostart", False)
        self.autorestart = config.get("autorestart", "never")
        self.exitcodes = config.get("exitcodes", [0])
        self.startretries = config.get("startretries", 0)
        self.starttime = config.get("starttime", 1)
        self.stopsignal = get_signal(config.get("stopsignal", "TERM"))
        self.stoptime = config.get("stoptime", 5)
        self.user = validate_user(config.get("user"))
        self.process = None
        self.state = "stopped"
        self.ever_running = False

        if not os.path.isdir(self.cwd):
            logger.warning(
                "Service '%s': working directory '%s' does not exist, using current directory instead.",
                self.name, self.cwd
            )
            self.cwd = os.getcwd()

    async def start(self):
        """Start the service process asynchronously. Returns True if started, False if already running."""
        if self.process and self.process.poll() is None:
            logger.warning("Service '%s' is already running.", self.name)
            return False
        current_user = getpass.getuser()
        if self.user and self.user != current_user and os.geteuid() != 0:
            logger.error("Service '%s': cannot start as user '%s' (current user: '%s').", self.name, self.user, current_user)
            self.state = "fatal"
            return False
        logger.info("Starting service '%s'...", self.name)
        stdout_fd, stderr_fd = open_streams(self.stdout_path, self.stderr_path)

        def preexec():
            os.setsid()
            os.umask(self.umask)

        args = shlex.split(self.cmd)
        try:
            self.process = subprocess.Popen( # Creation of the child process
                args,
                cwd=self.cwd,
                env=self.env,
                stdout=stdout_fd or subprocess.DEVNULL,
                stderr=stderr_fd or subprocess.DEVNULL,
                preexec_fn=preexec, # Create a new process group
            )
            self.state = "starting"
            logger.info("Service '%s' started (pid=%d).", self.name, self.process.pid)

            # Wait asynchronously for starttime to confirm it's alive
            await asyncio.sleep(self.starttime)
            
            if self.process.poll() is None:
                self.state = "running"
                self.ever_running = True
                logger.info("Service '%s' is now running.", self.name)
                return True
            else:
                code = self.process.returncode
                logger.error("Service '%s' exited early with code %s.", self.name, code)
                self.state = "stopped"
                return False

        except FileNotFoundError:
            logger.error("Command not found for service '%s': %s", self.name, self.cmd)
            self.state = "fatal"
            return False

        except Exception as e:
            logger.error("Failed to start service '%s': %s", self.name, e)
            self.state = "fatal"
            return False
        finally:
            if stdout_fd and not stdout_fd.closed:
                stdout_fd.close()
            if stderr_fd and not stderr_fd.closed:
                stderr_fd.close()

    async def stop(self):
        """Stop the service gracefully, then force kill if needed. Returns True if stopped, False if already stopped."""
        if not self.process or self.process.poll() is not None:
            logger.info("Service '%s' is not running.", self.name)
            self.state = "stopped"
            return False

        pid = self.process.pid
        logger.info("Stopping service '%s' (pid=%d)...", self.name, pid)
        self.state = "stopping"

        try:
            os.killpg(os.getpgid(pid), self.stopsignal)
        except ProcessLookupError:
            logger.warning("Process group not found for '%s'.", self.name)
            self.state = "stopped"
            return True
        except Exception as e:
            logger.error("Error sending stop signal to '%s': %s", self.name, e)

        # Wait asynchronously for graceful stop
        for _ in range(int(self.stoptime * 3)):
            if self.process.poll() is not None:
                logger.info("Service '%s' stopped gracefully.", self.name)
                self.state = "stopped"
                return True
            await asyncio.sleep(0.3)

        # Force kill if needed
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            logger.warning("Service '%s' force killed after timeout.", self.name)
        except Exception as e:
            logger.error("Failed to kill service '%s': %s", self.name, e)

        self.state = "stopped"
        return True

    async def restart(self):
        """Restart the service asynchronously."""
        logger.info("Restarting service '%s'...", self.name)
        await self.stop()
        await asyncio.sleep(0.2)
        await self.start()

    def check_status(self):
        """Return a short dict with current service status."""
        running = self.process and self.process.poll() is None
        pid = self.process.pid if running else None
        retcode = None if running else (self.process.returncode if self.process else None)
        return {
            "name": self.name,
            "state": self.state,
            "running": running,
            "pid": pid,
            "returncode": retcode,
            "autorestart": self.autorestart,
        }