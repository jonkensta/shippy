"""Pydantic models for configuration checking."""

from pydantic import BaseModel, HttpUrl, PositiveFloat


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
    parcel: ParcelConfig = ParcelConfig()
