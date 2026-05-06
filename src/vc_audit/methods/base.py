"""Strategy-pattern interface every valuation method satisfies.

Methods are stateless and side-effect-free. They receive the full request and return
a complete `MethodResult` including their own confidence score. The Triangulator (T7)
asks each method whether it is applicable, runs the applicable ones, and synthesizes.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from vc_audit.models import MethodResult, ValuationRequest


class ValuationMethod(ABC):
    """Abstract base class for all valuation methods."""

    name: ClassVar[str]

    @abstractmethod
    def is_applicable(self, request: ValuationRequest) -> bool:
        """Return True iff `request` carries the inputs this method needs."""

    @abstractmethod
    def value(self, request: ValuationRequest) -> MethodResult:
        """Run the method and return a self-describing result.

        Callers must ensure `is_applicable(request)` is True; behavior on missing inputs
        is undefined.
        """


class NoApplicableMethodError(Exception):
    """Raised by the Triangulator when no registered method applies to a request."""
