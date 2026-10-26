"""Internal domain request handlers, one module per endpoint."""

from internal.handlers.live import liveness
from internal.handlers.ready import readiness
from internal.handlers.root import service_info

__all__ = ["liveness", "readiness", "service_info"]
