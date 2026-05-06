"""Source attribution attached to a method's output."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Citation(BaseModel):
    """Where a piece of data came from. Every method output carries at least one."""

    model_config = ConfigDict(frozen=True)

    source: str  # e.g. "CompsProvider:mock_universe_v1"
    description: str
    retrieved_at: datetime
    url: str | None = None
