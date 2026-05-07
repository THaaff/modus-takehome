"""Composition root: wires the default Triangulator + provider stack.

Both the FastAPI app and the Typer CLI build their engine through this module so the
two presentation surfaces remain paper-thin wrappers over a single engine instance.
Tests can construct alternative `Triangulator`s directly when they need different
methods or providers.
"""

from vc_audit.data.comps_provider import MockCompsProvider
from vc_audit.data.index_provider import MockMarketIndexProvider
from vc_audit.engine.triangulator import Triangulator
from vc_audit.methods import (
    CompsMethod,
    DCFMethod,
    LastRoundMethod,
    MethodDescriptor,
)


def build_default_triangulator() -> Triangulator:
    """Wire `MockCompsProvider` + `MockMarketIndexProvider` + the three methods."""
    comps = MockCompsProvider()
    index = MockMarketIndexProvider()
    return Triangulator(
        [
            CompsMethod(comps),
            LastRoundMethod(index),
            DCFMethod(),
        ]
    )


def default_method_descriptors() -> list[MethodDescriptor]:
    """Return the descriptors for the methods registered by `build_default_triangulator`."""
    return [
        CompsMethod.describe(),
        LastRoundMethod.describe(),
        DCFMethod.describe(),
    ]
