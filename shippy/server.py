"""Client for the IBP FastAPI backend.

All endpoints shippy uses are unauthenticated, read-only GETs returning JSON.
The backend is served under the ``/api`` root path behind nginx (e.g.
``http://host/api``) but also answers path-stripped on port 8000 directly
(e.g. ``http://host:8000``); both base URL forms work here because the base is
normalized to end with a single trailing slash before joining paths
(otherwise ``urljoin`` would drop an ``/api`` prefix).
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


class ServerError(Exception):
    """A client error (4xx) reported by the IBP server, e.g. an unknown request.

    ``detail`` is the human-readable reason from the server's JSON body.
    """

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def to_easypost_address(name: str, data: dict[str, typing.Any]) -> dict[str, str]:
    """Build the 6-field address dict expected by shipping.build_address."""
    return {
        "name": name,
        "street1": data["street1"],
        "street2": data.get("street2") or "",
        "city": data["city"],
        "state": data["state"],
        "zipcode": data["zipcode"],
    }


class Server:
    """Server API convenience class."""

    _url: str
    _timeout: float

    def __init__(self, url: str, timeout: float = 30.0):
        """Create server API convenience class from a base url."""
        # Ensure exactly one trailing slash so urljoin preserves any path
        # prefix (e.g. "http://host/api" -> "http://host/api/").
        self._url = url.rstrip("/") + "/"
        self._timeout = float(timeout)

    @classmethod
    def from_config(cls, config: IbpConfig) -> "Server":
        """Create a Server instance from a Pydantic config object."""
        return cls(url=str(config.url))

    def _get(self, path: str) -> typing.Any:
        url = urljoin(self._url, path.lstrip("/"))
        response = requests.get(url, timeout=self._timeout)

        if 400 <= response.status_code < 500:
            raise ServerError(response.status_code, _error_detail(response))

        response.raise_for_status()
        return response.json()

    def shipping_settings(self) -> dict[str, typing.Any]:
        """Get the return address and unit recipient name (GET /shipping-settings)."""
        return self._get("shipping-settings")

    def return_address(self) -> dict[str, str]:
        """Get the EasyPost-ready organization return address."""
        return_address = self.shipping_settings()["return_address"]
        return to_easypost_address(return_address["name"], return_address)

    def units(self) -> list[dict[str, typing.Any]]:
        """Get the list of all units (GET /units)."""
        return self._get("units")

    def unit(self, jurisdiction: str, name: str) -> dict[str, typing.Any]:
        """Get a unit keyed by (jurisdiction, name)."""
        jurisdiction = normalize_jurisdiction(jurisdiction)
        return self._get(f"units/{jurisdiction}/{quote(name, safe='')}")

    def request_address(self, request_id: int) -> dict[str, typing.Any]:
        """Get the shipping address for a legacy (bare integer) request label."""
        return self._get(f"inmates/by-request/{request_id:d}/address")

    def inmate_request_address(
        self, jurisdiction: str, inmate_id: int, request_index: int
    ) -> dict[str, typing.Any]:
        """Get the shipping address for a new-style JUR-ID-INDEX request label."""
        jurisdiction = normalize_jurisdiction(jurisdiction)
        return self._get(
            f"inmates/{jurisdiction}/{inmate_id:d}"
            f"/requests/{request_index:d}/address"
        )


def _error_detail(response: requests.Response) -> str:
    """Extract FastAPI's ``{"detail": ...}`` message from an error response."""
    try:
        detail = response.json()["detail"]
    except (ValueError, KeyError, TypeError):
        return f"HTTP {response.status_code}: {response.text.strip()}"

    return detail if isinstance(detail, str) else str(detail)
