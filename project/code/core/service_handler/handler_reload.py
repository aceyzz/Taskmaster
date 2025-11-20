import asyncio
import json
import copy
from utils.logger import logger
from utils.config import Config
from core.service import Service


class ReloadMixin:
    """Mixin providing dynamic configuration reload (SIGHUP behavior)."""

    async def reload(self, config_path=None, email=None):
        """Reload configuration and apply all necessary changes."""
        logger.info("Reloading configuration (SIGHUP)...")
        path = config_path or self.config_path
        if not path:
            logger.error("No configuration path set for reload.")
            return

        try:
            cfg = Config(path)
            new_services = {s["name"]: s for s in cfg.services}
        except Exception as e:
            logger.error("Failed to reload config: %s", e)
            return

        async with self._lock:
            removed = [n for n in self.services if n not in new_services]
            added = [n for n in new_services if n not in self.services]

            # Remove obsolete services
            for name in removed:
                logger.info("Removing obsolete service '%s'.", name)
                await self._stop_nolock(name)
                del self.services[name]
                del self.service_configs[name]

            # Add new services
            for name in added:
                cfg_svc = new_services[name]
                logger.info("Adding new service '%s'.", name)
                self.service_configs[name] = copy.deepcopy(cfg_svc)
                self.services[name] = [Service(cfg_svc) for _ in range(cfg_svc.get("numprocs", 1))]
                
                if cfg_svc.get("autostart"):
                    logger.info("[Reload] Auto-starting new service '%s'...", name)
                    await self._start_nolock(name)
                else:
                    logger.info("[Reload] Service '%s' has autostart=False, not starting.", name)

            # Update modified services
            for name, new_cfg in new_services.items():
                if name not in self.service_configs:
                    continue
                old_cfg = self.service_configs[name]

                if self._config_changed(old_cfg, new_cfg):
                    logger.info("Updating modified service '%s'.", name)
                    await self._stop_nolock(name)
                    await asyncio.sleep(0.1)
                    self.service_configs[name] = copy.deepcopy(new_cfg)
                    self.services[name] = [
                        Service(new_cfg) for _ in range(new_cfg.get("numprocs", 1))
                    ]
                    if new_cfg.get("autostart"):
                        await self._start_nolock(name)
                else:
                    logger.debug("Service '%s' unchanged; keeping existing instances.", name)

            self.config_path = path
            if email is not None:
                self.email = email

            logger.info("Reload complete.")
            return bool(added or removed)

    def _config_changed(self, old_cfg, new_cfg):
        """Check if configuration has changed between old and new."""
        # Filter out runtime or auto-normalized keys
        ignored_keys = {"_internal", "env"}

        comparable_old = {k: v for k, v in old_cfg.items() if k not in ignored_keys}
        comparable_new = {k: v for k, v in new_cfg.items() if k not in ignored_keys}

        # Force umask back to string form for fair comparison
        if "umask" in comparable_old:
            comparable_old["umask"] = str(comparable_old["umask"])
        if "umask" in comparable_new:
            comparable_new["umask"] = str(comparable_new["umask"])

        return self._canonical(comparable_old) != self._canonical(comparable_new)

    def _canonical(self, obj):
        """Normalize configuration object for comparison."""
        def normalize(v):
            if isinstance(v, list):
                return sorted(map(normalize, v))
            if isinstance(v, dict):
                return {k: normalize(v) for k, v in sorted(v.items())}
            if isinstance(v, (int, float, str, bool)):
                return str(v)
            return v
        return json.dumps(normalize(obj), sort_keys=True)