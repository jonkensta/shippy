"""IBP server API abstraction."""

import json
from urllib.parse import urljoin

import requests
from easypost.models import Shipment as EasyPostShipment


class Server:
    """Server API convenience class."""

    def __init__(self, url, apikey, timeout: float = 30.0):
        """Create server API convenience class from url and apikey."""
        self._url = url
        self._apikey = apikey
        self._timeout = float(timeout)

    def _post(self, path, **kwargs):
        url = urljoin(self._url, path)
        kwargs["key"] = self._apikey
        response = requests.post(url, data=kwargs, timeout=self._timeout)
        response.raise_for_status()
        return json.loads(response.text)

    def unit_ids(self) -> dict[str, int]:
        """Get list of unit names with ids."""
        return self._post("unit_autoids")

    def return_address(self) -> dict[str, str]:
        """Get configured return address."""
        return self._post("return_address")

    def unit_address(self, autoid) -> dict[str, str]:
        """Get unit address from its id."""
        return self._post(f"unit_address/{autoid:d}")

    def _request_address_autoid(self, autoid):
        """Get address for a request given its autoid."""
        return self._post(f"request_address/{autoid:d}")

    def request_address(self, autoid) -> dict[str, str]:
        """Get address for a request given its request identifier."""
        return self._post(f"request_address/{autoid:d}")

    def ship(
        self,
        shipment: EasyPostShipment,
        request_ids: list[int] | None = None,
        unit_autoid: int | None = None,
    ):
        """Ship a shipment with optional request autoid."""
        if request_ids is None:
            request_ids = []

        rate_dollars = float(shipment.selected_rate.rate)
        rate_cents = int(round(100 * rate_dollars))
        weight = int(shipment.parcel.weight)
        data = {
            "postage": rate_cents,
            "weight": weight,
            "tracking_code": shipment.tracking_code,
            "tracking_url": shipment.tracker.public_url,
            **{f"request_ids-{k}": v for k, v in enumerate(request_ids)},
            "unit_autoid": unit_autoid,
        }
        return self._post("ship_requests", **data)
