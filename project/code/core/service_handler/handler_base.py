import asyncio
import copy
from typing import Any, Dict, List, Optional

from utils.logger import logger
from core.service import Service
from .handler_lifecycle import LifecycleMixin
from .handler_monitor import MonitorMixin
from .handler_reload import ReloadMixin


class ServiceHandler(LifecycleMixin, MonitorMixin, ReloadMixin):
    """
    Main orchestrator for all Service instances.
    Combines lifecycle management, monitoring, and dynamic reload behavior.
    """

    def __init__(
        self,
        services: List[Dict[str, Any]],
        email: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        self.services: Dict[str, List[Service]] = {}
        self.service_configs: Dict[str, Dict[str, Any]] = {}
        self.email = email
        self.config_path = config_path
        self._lock = asyncio.Lock()

        # Initialize services
        for svc_cfg in services:
            name = svc_cfg.get("name")
            if not name:
                logger.error("Skipping unnamed service: %s", svc_cfg)
                continue

            self.service_configs[name] = copy.deepcopy(svc_cfg)
            numprocs = svc_cfg.get("numprocs", 1)
            instances = [Service(svc_cfg) for _ in range(numprocs)]
            self.services[name] = instances

        logger.info("ServiceHandler initialized with %d service groups.", len(self.services))