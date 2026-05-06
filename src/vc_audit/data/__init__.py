"""Data provider interfaces and (later) mock implementations."""

from vc_audit.data.comps_provider import Comp, CompsProvider
from vc_audit.data.index_provider import MarketIndexProvider

__all__ = ["Comp", "CompsProvider", "MarketIndexProvider"]
