"""IBP server API abstraction."""

import json
from urllib.parse import urljoin

import requests

from .models import IbpConfig


class Server:
    """Server API convenience class."""

    _url: str
    _apikey: str
    _timeout: float

    def __init__(self, url: str, apikey: str, timeout: float = 30.0):
        """Create server API convenience class from url and apikey."""
        self._url = url
        self._apikey = apikey
        self._timeout = float(timeout)

    @classmethod
    def from_config(cls, config: IbpConfig) -> "Server":
        """Create a Server instance from a Pydantic config object."""
        return cls(url=str(config.url), apikey=config.apikey)

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
