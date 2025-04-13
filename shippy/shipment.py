"""Postage convenience functions."""

import easypost

from easypost.models import Address as EasyPostAddress
from easypost.models import Parcel as EasyPostParcel
from easypost.models import Shipment as EasyPostShipment


# pylint: disable=too-few-public-methods
class Builder:
    """Shipment builder."""

    def __init__(self, apikey: str):
        """Initialize shipment builder with an apikey."""
        self._client = easypost.EasyPostClient(apikey)

    def _build_address(self, **kwargs) -> EasyPostAddress:
        """Build easypost Address."""
        kwargs["zip"] = kwargs.pop("zipcode")
        kwargs["country"] = "US"
        kwargs["phone"] = ""
        return self._client.address.create_and_verify(**kwargs)

    def _build_parcel(self, weight: int) -> EasyPostParcel:
        """Build easypost Parcel given weight in ounces."""
        return self._client.parcel.create(predefined_package="Parcel", weight=weight)

    def _build_shipment(self, from_address: dict, to_address: dict, weight: int) -> EasyPostShipment:
        """Build easypost Shipment given addresses and weight in ounces."""
        return self._client.shipment.create(
            from_address=self._build_address(**from_address),
            to_address=self._build_address(**to_address),
            parcel=self._build_parcel(weight),
            options=dict(special_rates_eligibility="USPS.LIBRARYMAIL"),
        )

    def __call__(self, from_address: dict, to_address: dict, weight: int) -> EasyPostShipment:
        """Purchase postage given addresses and weight in ounces."""
        shipment = self._build_shipment(from_address, to_address, weight)
        rate = shipment.lowest_rate(["USPS"])
        return self._client.shipment.buy(shipment.id, rate=rate)


def extract_data(shipment):
    """Extract useful data from easypost shipment object."""
    return dict(
        postage=int(round(100 * float(shipment.selected_rate.rate))),
        weight=int(shipment.parcel.weight),
        tracking_code=shipment.tracking_code,
        tracking_url=shipment.tracker.public_url,
    )
