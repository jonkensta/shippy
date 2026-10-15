"""Postage convenience functions."""

from dataclasses import dataclass
from typing import Optional

from easypost import EasyPostClient
from easypost.models import Address as EasyPostAddress
from easypost.models import Shipment as EasyPostShipment

# Below this weight Library Mail is always cheaper than Ground Advantage, so
# the box size can't change the rate and volunteers aren't asked about it.
BOX_QUESTION_MIN_LB = 4

# Services shown side by side before buying (EasyPost service names).
COMPARED_SERVICES = ("LibraryMail", "GroundAdvantage")

SERVICE_NAMES = {
    "LibraryMail": "Library Mail",
    "GroundAdvantage": "Ground Advantage",
    "MediaMail": "Media Mail",
    "Priority": "Priority Mail",
}


def build_address(client: EasyPostClient, **kwargs) -> EasyPostAddress:
    """Build easypost Address."""
    kwargs["zip"] = kwargs.pop("zipcode")
    kwargs["country"] = "US"
    kwargs["phone"] = ""
    return client.address.create(**kwargs)


def quote_shipment(  # pylint: disable=too-many-arguments
    client: EasyPostClient,
    from_address: EasyPostAddress,
    to_address: EasyPostAddress,
    weight: float,
    dimensions: tuple[float, float, float],
) -> EasyPostShipment:
    """Create a shipment (rates quoted, nothing bought); weight in ounces."""
    length, width, height = dimensions
    parcel = client.parcel.create(
        predefined_package="Parcel",
        weight=weight,
        length=length,
        width=width,
        height=height,
    )
    return client.shipment.create(
        from_address=from_address,
        to_address=to_address,
        parcel=parcel,
        options={"special_rates_eligibility": "USPS.LIBRARYMAIL"},
    )


def cheapest_rate(shipment: EasyPostShipment):
    """The cheapest USPS rate quoted for ``shipment``."""
    return shipment.lowest_rate(["USPS"])


def buy_shipment(
    client: EasyPostClient, shipment: EasyPostShipment, rate
) -> EasyPostShipment:
    """Buy ``rate`` for a quoted shipment."""
    return client.shipment.buy(shipment.id, rate=rate)


def service_name(service: str) -> str:
    """Volunteer-facing name of an EasyPost service."""
    return SERVICE_NAMES.get(service, service)


@dataclass(frozen=True)
class RateSummary:
    """What to show before buying: the price comparison and any warning."""

    line: str
    warning: Optional[str] = None


def summarize_rates(rates, chosen) -> RateSummary:
    """Compare Library Mail and Ground Advantage and name the rate being bought.

    ``rates`` are the shipment's quoted rates (objects with ``carrier``,
    ``service`` and ``rate``); ``chosen`` is the rate about to be bought.
    """
    quoted: dict[str, float] = {}
    for rate in rates:
        if rate.carrier == "USPS" and rate.service in COMPARED_SERVICES:
            price = float(rate.rate)
            quoted[rate.service] = min(price, quoted.get(rate.service, price))

    parts = [
        f"{service_name(service)} ${quoted[service]:.2f}"
        for service in COMPARED_SERVICES
        if service in quoted
    ]
    chosen_name = service_name(chosen.service)
    buying = f"{chosen_name} ${float(chosen.rate):.2f} (cheapest)"
    line = f"{' · '.join(parts)} → buying {buying}" if parts else f"Buying {buying}"

    warning = None
    if "LibraryMail" not in quoted:
        warning = (
            "No Library Mail rate was quoted for this package, so it is not "
            "being sent Library Mail. Check the address and weight if that "
            "is unexpected."
        )
    return RateSummary(line=line, warning=warning)
