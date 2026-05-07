"""Triangulation engine."""

from vc_audit.engine.factory import build_default_triangulator, default_method_descriptors
from vc_audit.engine.triangulator import Triangulator

__all__ = [
    "Triangulator",
    "build_default_triangulator",
    "default_method_descriptors",
]
