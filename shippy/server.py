"""Client for the IBP FastAPI backend.

All endpoints are unauthenticated GETs returning JSON. The backend is served
under the ``/api`` root path behind nginx (e.g. ``https://host/api``) but also
answers path-stripped on port 8000 directly (e.g. ``http://host:8000``); both
base URL forms work here because the base is normalized to end with a single
trailing slash before joining paths (otherwise ``urljoin`` would drop an
``/api`` prefix).
"""

import typing
from urllib.parse import quote, urljoin

import requests

from .models import IbpConfig

JURISDICTIONS = {
    "TEX": "Texas",
    "TEXAS": "Texas",
    "FED": "Federal",
    "FEDERAL": "Federal",
}
"""Map of label jurisdiction codes to backend jurisdiction names."""


def normalize_jurisdiction(jurisdiction: str) -> str:
    """Normalize a jurisdiction code (e.g. "TEX") to a backend name."""
    try:
        return JURISDICTIONS[jurisdiction.strip().upper()]
    except KeyError:
        raise ValueError(f"Unknown jurisdiction: {jurisdiction!r}") from None


class Server:
    """Server API convenience class."""

    _url: str
    _unit_address_name: str
    _timeout: float

    def __init__(self, url: str, unit_address_name: str, timeout: float = 30.0):
        """Create server API convenience class from a base url."""
        # Ensure exactly one trailing slash so urljoin preserves any path
        # prefix (e.g. "https://host/api" -> "https://host/api/").
        self._url = url.rstrip("/") + "/"
        self._unit_address_name = unit_address_name
        self._timeout = float(timeout)

    @classmethod
    def from_config(cls, config: IbpConfig) -> "Server":
        """Create a Server instance from a Pydantic config object."""
        return cls(url=str(config.url), unit_address_name=config.unit_address_name)

    def _get(self, path: str) -> typing.Any:
        url = urljoin(self._url, path.lstrip("/"))
        response = requests.get(url, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def units(self) -> list[dict[str, typing.Any]]:
        """Get the list of all units from GET /units."""
        return self._get("units")

    def unit_address(self, jurisdiction: str, name: str) -> dict[str, str]:
        """Get an EasyPost-ready address for a unit keyed by (jurisdiction, name)."""
        jurisdiction = normalize_jurisdiction(jurisdiction)
        unit = self._get(f"units/{jurisdiction}/{quote(name, safe='')}")
        return self._build_address(self._unit_address_name, unit)

    def request_address(self, request_id: int) -> dict[str, str]:
        """Get an address for a legacy request ID (old-style bare-number labels)."""
        inmate = self._get(f"inmates/by-request/{request_id:d}")
        return self._inmate_address(inmate)

    def inmate_address(self, jurisdiction: str, inmate_id: int) -> dict[str, str]:
        """Get an address for an inmate (new-style JUR-ID-INDEX labels)."""
        jurisdiction = normalize_jurisdiction(jurisdiction)
        inmate = self._get(f"inmates/{jurisdiction}/{inmate_id:d}")
        return self._inmate_address(inmate)

    def _inmate_address(self, inmate: dict[str, typing.Any]) -> dict[str, str]:
        """Build an EasyPost-ready address from an inmate object."""
        unit = inmate.get("unit")
        if unit is None:
            raise LookupError("inmate is not assigned to a unit")

        first_name = (inmate.get("first_name") or "").title()
        last_name = (inmate.get("last_name") or "").title()
        name = f"{first_name} {last_name} #{inmate['id']:08d}"
        return self._build_address(name, unit)

    @staticmethod
    def _build_address(name: str, unit: dict[str, typing.Any]) -> dict[str, str]:
        """Build the 6-field address dict expected by shipping.build_address."""
        return {
            "name": name,
            "street1": unit["street1"],
            "street2": unit.get("street2") or "",
            "city": unit["city"],
            "state": unit["state"],
            "zipcode": unit["zipcode"],
        }
