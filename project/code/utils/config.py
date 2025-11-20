from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import yaml
from cerberus import Validator
from utils.logger import logger


class ConfigError(Exception):
    """Raised when the configuration file is invalid."""


class Config:
    """
    Handles reading and full validation of the Taskmaster configuration file.
    
    Supports TWO formats:
    1. Subject format: programs: {name: {config...}}  (dict of dicts)
    2. Internal format: services: [{name: ..., config...}]  (list of dicts)

    Attributes:
        path: Path to the YAML configuration file.
        raw: Raw YAML content as a Python dictionary.
        services: List of validated and normalized service definitions.
        email: Optional global email configuration block.
    """

    def __init__(self, path: str):
        self.path = path
        self.raw: Optional[Dict[str, Any]] = None
        self.services: List[Dict[str, Any]] = []
        self.email: Optional[Dict[str, Any]] = None

        self._load_yaml()
        self._basic_checks()
        self.validate_with_cerberus()

    def _load_yaml(self) -> None:
        """Load YAML file and handle basic errors."""
        if not os.path.exists(self.path):
            msg = f"Configuration file not found: {self.path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        with open(self.path, "r", encoding="utf-8") as fh:
            content = fh.read()
            if not content.strip():
                msg = "Empty configuration file"
                logger.error(msg)
                raise ConfigError(msg)

            try:
                parsed = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                msg = f"YAML parsing error: {exc}"
                logger.error(msg)
                raise

            if parsed is None or not isinstance(parsed, dict):
                msg = "Invalid or empty YAML structure"
                logger.error(msg)
                raise ConfigError(msg)

            self.raw = parsed
            logger.debug("Raw configuration loaded: %s", self.raw)

    def _basic_checks(self) -> None:
        """
        Ensure root-level keys and types are correct before deep validation.
        Supports both 'programs' (subject format) and 'services' (internal format).
        """
        if "programs" not in self.raw and "services" not in self.raw:
            msg = (
                "Missing 'programs' or 'services' key in configuration file.\n"
                "Expected format:\n"
                "  programs:           (recommended - subject format)\n"
                "    program_name:\n"
                "      cmd: ...\n"
                "      numprocs: ...\n"
                "  OR\n"
                "  services:           (alternative - list format)\n"
                "    - name: program_name\n"
                "      cmd: ...\n"
                "      numprocs: ..."
            )
            logger.error(msg)
            raise ConfigError(msg)

        if "programs" in self.raw:
            programs = self.raw.get("programs")
            if not isinstance(programs, dict):
                msg = "The 'programs' key must be a dictionary/mapping"
                logger.error(msg)
                raise ConfigError(msg)
            
            services_list = []
            for program_name, program_config in programs.items():
                if not isinstance(program_config, dict):
                    msg = f"Program '{program_name}' must be a dictionary"
                    logger.error(msg)
                    raise ConfigError(msg)
                
                service = {"name": program_name}
                service.update(program_config)
                services_list.append(service)
            
            self.services = services_list
            logger.info(f"Configuration loaded successfully (programs format): {len(services_list)} program(s)")
        
        elif "services" in self.raw:
            services = self.raw.get("services")
            if not isinstance(services, list):
                msg = "The 'services' key must be a list of service mappings"
                msg = (
                    "The 'services' key must be a list of service mappings.\n"
                    "Expected format:\n"
                    "  services:\n"
                    "    - name: service1\n"
                    "      cmd: /bin/sleep 30\n"
                    "      numprocs: 1\n"
                    "      ...\n"
                    "\n"
                    "Or use the recommended 'programs' format (dict):\n"
                    "  programs:\n"
                    "    service1:\n"
                    "      cmd: /bin/sleep 30\n"
                    "      numprocs: 1\n"
                    "      ..."
                )
                logger.error(msg)
                raise ConfigError(msg)
            
            self.services = services
            logger.info(f"Configuration loaded successfully (services format): {len(services)} service(s)")

        if "email" in self.raw:
            if not isinstance(self.raw["email"], dict):
                msg = "The 'email' key must be a mapping/dictionary"
                logger.error(msg)
                raise ConfigError(msg)
            self.email = self.raw["email"]

    def validate_with_cerberus(self) -> None:
        """Validate the configuration content using a strict Cerberus schema."""
        schema = {
            "services": {
                "type": "list",
                "minlength": 1,
                "schema": {
                    "type": "dict",
                    "schema": {
                        "name": {"type": "string", "empty": False, "required": True},
                        "cmd": {"type": "string", "empty": False, "required": True},
                        "numprocs": {
                            "type": "integer",
                            "min": 1,
                            "max": 32,
                            "required": True,
                        },
                        "umask": {
                            "type": ["integer", "string"],
                            "required": True,
                            "check_with": self._validate_umask,
                        },
                        "workingdir": {
                            "type": "string",
                            "empty": False,
                            "required": True,
                            "check_with": self._validate_workingdir,
                        },
                        "autostart": {"type": "boolean", "required": True},
                        "autorestart": {
                            "type": "string",
                            "allowed": ["always", "never", "unexpected"],
                            "required": True,
                        },
                        "exitcodes": {
                            "type": "list",
                            "schema": {"type": "integer"},
                            "minlength": 1,
                            "required": True,
                        },
                        "startretries": {"type": "integer", "min": 0, "required": True},
                        "starttime": {"type": "integer", "min": 0, "required": True},
                        "stopsignal": {"type": "string", "empty": False, "required": True},
                        "stoptime": {"type": "integer", "min": 0, "required": True},
                        "user": {"type": "string", "required": False},
                        "stdout": {"type": "string", "required": False},
                        "stderr": {"type": "string", "required": False},
                        "env": {
                            "type": "dict",
                            "keysrules": {"type": "string"},
                            "valuesrules": {"type": "string"},
                            "required": False,
                            "check_with": self._validate_env,
                        },
                    },
                },
            },
            "email": {
                "type": "dict",
                "required": False,
                "schema": {
                    "to": {"type": "string", "required": False},
                    "smtp_email": {"type": "string", "required": False},
                    "smtp_password": {"type": "string", "required": False},
                    "smtp_server": {"type": "string", "required": False},
                    "smtp_port": {"type": "integer", "required": False},
                },
            },
        }

        validation_doc = {"services": self.services}
        if self.email:
            validation_doc["email"] = self.email

        v = Validator(schema, require_all=False)
        if not v.validate(validation_doc):
            errors_str = self._format_cerberus_errors(v.errors)
            msg = f"Configuration validation failed:\n{errors_str}"
            logger.error(msg)
            raise ConfigError(msg)

        logger.info("Configuration validation successful (Cerberus).")

    def _format_cerberus_errors(self, errors: dict, indent: int = 0) -> str:
        """Recursively format Cerberus validation errors into a readable string."""
        lines = []
        prefix = "  " * indent
        for key, value in errors.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_cerberus_errors(value, indent + 1))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}{key}:")
                        lines.append(self._format_cerberus_errors(item, indent + 1))
                    else:
                        lines.append(f"{prefix}{key}: {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)

    def _validate_umask(self, field, value, error):
        """Custom validator for umask field (must be a valid octal between 0 and 0o777)."""
        try:
            if isinstance(value, str):
                umask_int = int(value, 8)
            else:
                umask_int = int(value)
            if not (0 <= umask_int <= 0o777):
                error(field, "umask must be between 0 and 0o777 (octal 000-777)")
        except (ValueError, TypeError):
            error(field, "umask must be a valid octal number (int or string)")

    def _validate_workingdir(self, field, value, error):
        """Custom validator for workingdir field (must be a non-empty string)."""
        if not isinstance(value, str) or not value.strip():
            error(field, "workingdir must be a non-empty string")

    def _validate_env(self, field, value, error):
        """Custom validator for env field (must be a dict of string: string)."""
        if not isinstance(value, dict):
            error(field, "env must be a dictionary")
            return
        for k, v in value.items():
            if not isinstance(k, str) or not isinstance(v, str):
                error(field, f"env key-value pairs must be strings (got {k}={v})")

    def reload(self, path: Optional[str] = None) -> bool:
        """
        Reload configuration from file.
        
        Args:
            path: Optional new path to configuration file
            
        Returns:
            bool: True if configuration changed, False otherwise
        """
        if path:
            self.path = path
        
        old_services = self.services.copy()
        old_email = self.email.copy() if self.email else None
        
        try:
            self._load_yaml()
            self._basic_checks()
            self.validate_with_cerberus()
            
            changed = (self.services != old_services) or (self.email != old_email)
            
            if changed:
                logger.info("Configuration reloaded with changes")
            else:
                logger.info("Configuration reloaded without changes")
            
            return changed
            
        except Exception as e:
            self.services = old_services
            self.email = old_email
            logger.error(f"Failed to reload configuration: {e}")
            raise