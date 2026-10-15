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
    def small_box_is_one_cubic_foot(self) -> "ParcelConfig":
        """Require the declared small box to be exactly one cubic foot.

        Each side must be a whole number of inches. USPS rounds sides up to a
        whole inch for dimensional weight but cubic pricing rounds them down to
        the quarter inch, so a fractional side (e.g. 11.1, which rounds up to a
        12-inch cube) would be priced as a much smaller cubic tier. No side may
        pass the 22-inch surcharge length.

        The rounded volume must EQUAL 1,728 cubic inches, not just stay under
        it: EasyPost applies USPS cubic pricing, so a smaller declared box
        (e.g. 12x12x6) would put a qualifying real box (e.g. 12x12x12) in a
        lower cubic tier and buy too little postage. Declaring the top tier
        can never understate a box that qualifies.
        """
        # Known trade-off: always declaring the top tier means really small
        # boxes miss cheaper cubic tiers. Deferred to a future change that
        # declares real dimensions (or lets volunteers pick a box).
        given = (self.small_length, self.small_width, self.small_height)
        fractional = [side for side in given if not float(side).is_integer()]
        if fractional:
            raise ValueError(
                f"small box sides must be whole inches; got {fractional[0]:g}"
            )
        sides = [int(side) for side in given]
        volume = math.prod(sides)
        if volume != CUBIC_FOOT_IN3:
            raise ValueError(
                f"small box is {volume:g} cubic inches; it must be exactly "
                f"{CUBIC_FOOT_IN3:g} (one cubic foot)"
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
