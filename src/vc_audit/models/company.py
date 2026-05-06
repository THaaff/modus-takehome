"""Portfolio company identity."""

from pydantic import BaseModel, ConfigDict


class PortfolioCompany(BaseModel):
    """The private company being valued."""

    model_config = ConfigDict(frozen=True)

    name: str
    sector: str | None = None
