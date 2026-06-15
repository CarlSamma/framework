"""Structured logging setup using structlog.

Provides JSON output with correlation IDs, ISO timestamps, and log levels.
All modules use get_logger(name) for structured logging.
"""

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON output and correlation IDs.

    Call once at application startup before any logging occurs.

    Args:
        log_level: Minimum log level. One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a named structured logger.

    Args:
        name: Logger name, typically the module name (e.g., 'engine', 'db').

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)