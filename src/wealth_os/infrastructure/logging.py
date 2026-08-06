from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

from wealth_os.infrastructure.config import AppConfig

__all__ = ["configure_logging", "get_logger", "RunContext"]


class RunContext:
    """Binds run-level metadata to structured logs."""

    def __init__(
        self,
        run_id: str,
        config: AppConfig | None = None,
        data_version: str = "",
        strategy_version: str = "0.1.0",
        environment: str = "development",
    ) -> None:
        self.run_id = run_id
        self.config = config
        self.data_version = data_version
        self.strategy_version = strategy_version
        self.environment = environment

    @property
    def config_hash(self) -> str:
        if self.config is None:
            return "no-config"
        return _hash_config(self.config.model_dump())

    def as_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "strategy_version": self.strategy_version,
            "data_version": self.data_version,
            "environment": self.environment,
            "config_hash": self.config_hash,
        }


def _hash_config(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _add_context(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    ctx = structlog.contextvars.get_contextvars()
    if ctx:
        event_dict.update(ctx)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _add_context,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    import logging

    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper()))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
