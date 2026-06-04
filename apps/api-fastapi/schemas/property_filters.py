"""Validated filter contract for faceted property list queries."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

PropertyTypeFilter = Literal["venta", "alquiler"]


class PropertyFilterParams(BaseModel):
    """Optional facets combined with AND semantics."""

    source_portal: Optional[str] = None
    sector: Optional[str] = None
    keyword: Optional[str] = Field(default=None, max_length=120)
    price_min: Optional[float] = Field(default=None, ge=0)
    price_max: Optional[float] = Field(default=None, ge=0)
    bedrooms_min: Optional[int] = Field(default=None, ge=0, le=20)
    bathrooms_min: Optional[float] = Field(default=None, ge=0, le=20)
    property_type: Optional[PropertyTypeFilter] = None
    agency: Optional[str] = Field(default=None, max_length=120)

    @field_validator("keyword", "agency", "sector", "source_portal", mode="before")
    @classmethod
    def _strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("price_max")
    @classmethod
    def _price_range_valid(
        cls, price_max: Optional[float], info
    ) -> Optional[float]:
        price_min = info.data.get("price_min")
        if price_min is not None and price_max is not None and price_max < price_min:
            raise ValueError("price_max must be >= price_min")
        return price_max

    def cache_fingerprint(self) -> str:
        """Stable key for count-cache entries."""
        parts = [
            f"portal={self.source_portal or ''}",
            f"sector={self.sector or ''}",
            f"q={self.keyword or ''}",
            f"pmin={self.price_min if self.price_min is not None else ''}",
            f"pmax={self.price_max if self.price_max is not None else ''}",
            f"beds={self.bedrooms_min if self.bedrooms_min is not None else ''}",
            f"baths={self.bathrooms_min if self.bathrooms_min is not None else ''}",
            f"type={self.property_type or ''}",
            f"agency={self.agency or ''}",
        ]
        return "|".join(parts)