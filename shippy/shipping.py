"""Postage convenience functions."""

from easypost import EasyPostClient
from easypost.models import Address as EasyPostAddress
from easypost.models import Shipment as EasyPostShipment

from .models import ParcelConfig


def build_address(client: EasyPostClient, **kwargs) -> EasyPostAddress:
    """Build easypost Address."""
    kwargs["zip"] = kwargs.pop("zipcode")
    kwargs["country"] = "US"
    kwargs["phone"] = ""
    return client.address.create(**kwargs)


def build_shipment(
    client: EasyPostClient,
    from_address: EasyPostAddress,
    to_address: EasyPostAddress,
    weight: int,
    parcel_config: ParcelConfig,
) -> EasyPostShipment:
    """Purchase postage given addresses, weight in ounces, and parcel dimensions."""
    parcel = client.parcel.create(
        predefined_package="Parcel",
        weight=weight,
        length=parcel_config.length,
        width=parcel_config.width,
        height=parcel_config.height,
    )
    shipment = client.shipment.create(
        from_address=from_address,
        to_address=to_address,
        parcel=parcel,
        options={"special_rates_eligibility": "USPS.LIBRARYMAIL"},
    )
    rate = shipment.lowest_rate(["USPS"])
    return client.shipment.buy(shipment.id, rate=rate)
