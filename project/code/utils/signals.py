import signal
from utils.logger import logger

SIGNALS = {
    "TERM": signal.SIGTERM,
    "KILL": signal.SIGKILL,
    "USR1": signal.SIGUSR1,
    "USR2": signal.SIGUSR2,
    "INT": signal.SIGINT,
    "HUP": signal.SIGHUP,
    "QUIT": signal.SIGQUIT,
}

def get_signal(name: str):
    """Return signal object from name."""
    if not name:
        return signal.SIGTERM
    name = name.upper()
    if name in SIGNALS:
        return SIGNALS[name]
    logger.warning("Unknown signal '%s', defaulting to TERM", name)
    return signal.SIGTERM