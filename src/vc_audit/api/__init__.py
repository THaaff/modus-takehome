"""FastAPI app surface. The actual ``app`` is defined in ``server``."""

from vc_audit.api.server import app

__all__ = ["app"]
