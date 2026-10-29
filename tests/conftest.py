"""Shared fixtures: canned IBP server responses and an HTTP mock."""

import json
import typing
from unittest import mock

import pytest
import requests

BASE_URL = "http://ibp.test/api"

SHIPPING_SETTINGS = {
    "return_address": {
        "name": "Inside Books Project",
        "street1": "PO Box 301029",
        "street2": "12 ST BOOKS",
        "city": "Austin",
        "state": "TX",
        "zipcode": "78703",
    },
    "unit_recipient_name": "ATTN: MAILROOM STAFF",
}

UNIT = {
    "jurisdiction": "Texas",
    "name": "Hughes",
    "street1": "Rt 2 Box 4400",
    "street2": None,
    "city": "Gatesville",
    "state": "TX",
    "zipcode": "76597",
    "url": None,
    "shipping_method": "Box",
}


def request_address(**overrides: typing.Any) -> dict[str, typing.Any]:
    """Build a RequestAddress response body, with field overrides."""
    body = {
        "name": "Jane Doe #00012345",
        "first_name": "JANE",
        "last_name": "DOE",
        "jurisdiction": "Texas",
        "id": 12345,
        "datetime_fetched": "2099-01-01T00:00:00+00:00",
        "request_index": 0,
        "request_id": 98765,
        "action": "Filled",
        "unit_name": "Hughes",
        "street1": "Rt 2 Box 4400",
        "street2": None,
        "city": "Gatesville",
        "state": "TX",
        "zipcode": "76597",
        "shipping_method": "Individual",
        "unit_recipient_name": "ATTN: MAILROOM STAFF",
    }
    body.update(overrides)
    return body


def make_response(status_code: int, body: typing.Any) -> requests.Response:
    """Build a real requests.Response carrying a JSON body."""
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(body).encode()  # pylint: disable=protected-access
    response.headers["Content-Type"] = "application/json"
    return response


class FakeHttp:
    """Route mocked ``requests.get`` calls by URL to canned responses."""

    def __init__(self) -> None:
        self.routes: dict[str, requests.Response] = {}
        self.calls: list[str] = []

    def add(self, path: str, body: typing.Any, status_code: int = 200) -> None:
        """Serve ``body`` for GET {BASE_URL}/{path}."""
        self.routes[f"{BASE_URL}/{path}"] = make_response(status_code, body)

    def get(self, url: str, **_kwargs: typing.Any) -> requests.Response:
        """Stand-in for requests.get."""
        self.calls.append(url)
        try:
            return self.routes[url]
        except KeyError:
            return make_response(404, {"detail": "Not Found"})


@pytest.fixture(name="http")
def fixture_http() -> typing.Iterator[FakeHttp]:
    """Patch shippy's HTTP GETs with a FakeHttp router."""
    fake = FakeHttp()
    with mock.patch("shippy.server.requests.get", side_effect=fake.get):
        yield fake
