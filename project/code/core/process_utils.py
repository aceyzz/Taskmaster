import os
import pwd

from utils.logger import logger


def validate_user(user):
    """Return user if exists, otherwise None."""
    if not user:
        return None
    try:
        pwd.getpwnam(user)
        return user
    except KeyError:
        logger.warning("User '%s' not found, using current user", user)
        return None


def open_streams(stdout_path, stderr_path):
    """Try opening stdout/stderr files; return (stdout_fd, stderr_fd)."""
    stdout_fd, stderr_fd = None, None
    try:
        if stdout_path:
            stdout_fd = open(stdout_path, "a", buffering=1)
    except Exception as e:
        logger.error("Failed to open stdout file '%s': %s", stdout_path, e)
    try:
        if stderr_path:
            stderr_fd = open(stderr_path, "a", buffering=1)
    except Exception as e:
        logger.error("Failed to open stderr file '%s': %s", stderr_path, e)
    return stdout_fd, stderr_fd