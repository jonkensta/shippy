"""Pydantic models for configuration checking."""

from pydantic import BaseModel, HttpUrl, PositiveFloat, field_validator


class IbpConfig(BaseModel):
    """Model for IBP configuration.

    The new IBP FastAPI backend does not use API keys, so only the base URL
    is needed. ``unit_address_name`` is the recipient name injected into unit
    (bulk) addresses; the legacy server supplied this from its own config.
    """

    url: HttpUrl
    unit_address_name: str = "ATTN: MAILROOM STAFF"


class ReturnAddressConfig(BaseModel):
    """Model for the organization return address.

    The legacy server served this from server-side config; it now lives in
    shippy's own ``[return_address]`` config section.
    """

    name: str
    street1: str
    street2: str = ""
    city: str
    state: str
    zipcode: str

    @field_validator("name", "street1", "city", "state", "zipcode")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Ensure required address fields are not empty."""
        if not value.strip():
            raise ValueError("Required address fields cannot be empty")
        return value


class EasypostConfig(BaseModel):
    """Model for Easypost configuration."""

    apikey: str


class GoogleMapsConfig(BaseModel):
    """Model for Google Maps configuration."""

    apikey: str


class ParcelConfig(BaseModel):
    """Model for parcel dimensions in inches.

    USPS requires all three dimensions for the "Parcel" container type.
    Library Mail is priced by weight alone, so these just need to be large
    enough for any package while staying under the USPS nonstandard-size
    surcharge thresholds (22 inches per side, 2 cubic feet).
    """

    length: PositiveFloat = 20.0
    width: PositiveFloat = 14.0
    height: PositiveFloat = 10.0


class Config(BaseModel):
    """Model for application configuration."""

    ibp: IbpConfig
    easypost: EasypostConfig
    googlemaps: GoogleMapsConfig
    return_address: ReturnAddressConfig
    parcel: ParcelConfig = ParcelConfig()
