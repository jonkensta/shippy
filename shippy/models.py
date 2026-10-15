"""Pydantic models for configuration checking."""

import math

from pydantic import BaseModel, HttpUrl, PositiveFloat, model_validator

# USPS prices Ground Advantage by dimensional weight above one cubic foot.
CUBIC_FOOT_IN3 = 1728.0
# Above this length per side USPS adds Ground Advantage surcharges.
MAX_SIDE_IN = 22.0


class IbpConfig(BaseModel):
    """Model for IBP configuration."""

    url: HttpUrl
    apikey: str


class EasypostConfig(BaseModel):
    """Model for Easypost configuration."""

    apikey: str


class GoogleMapsConfig(BaseModel):
    """Model for Google Maps configuration."""

    apikey: str


class ParcelConfig(BaseModel):
    """Model for parcel dimensions in inches.

    USPS requires all three dimensions for the "Parcel" container type.
    Library Mail is priced by weight alone, so ``length``/``width``/``height``
    just need to be large enough for any package while staying under the USPS
    nonstandard-size surcharge thresholds (22 inches per side, 2 cubic feet).

    Ground Advantage is priced by dimensional weight above one cubic foot, so
    the large box never wins on price. Volunteers who say a heavier package is
    in a box of one cubic foot or less get the ``small_*`` dimensions instead,
    which must stay at or under one cubic foot.
    """

    length: PositiveFloat = 20.0
    width: PositiveFloat = 14.0
    height: PositiveFloat = 10.0
    small_length: PositiveFloat = 12.0
    small_width: PositiveFloat = 12.0
    small_height: PositiveFloat = 12.0

    @model_validator(mode="after")
    def small_box_within_cubic_foot(self) -> "ParcelConfig":
        """Reject a "small box" that USPS would price by dimensional weight.

        USPS rounds each side up to a whole inch before multiplying, so the
        check does too; and no side may pass the 22-inch surcharge length.
        """
        sides = [
            math.ceil(side)
            for side in (self.small_length, self.small_width, self.small_height)
        ]
        volume = math.prod(sides)
        if volume > CUBIC_FOOT_IN3:
            raise ValueError(
                f"small box is {volume:g} cubic inches after USPS rounds each "
                f"side up; it must be at most {CUBIC_FOOT_IN3:g} (one cubic foot)"
            )
        if max(sides) > MAX_SIDE_IN:
            raise ValueError(
                f"small box has a {max(sides):g}-inch side; no side may be "
                f"longer than {MAX_SIDE_IN:g} inches"
            )
        return self

    def dimensions(self, small_box: bool) -> tuple[float, float, float]:
        """(length, width, height) to declare for the chosen box."""
        if small_box:
            return (self.small_length, self.small_width, self.small_height)
        return (self.length, self.width, self.height)


class Config(BaseModel):
    """Model for application configuration."""

    ibp: IbpConfig
    easypost: EasypostConfig
    googlemaps: GoogleMapsConfig
    parcel: ParcelConfig = ParcelConfig()
