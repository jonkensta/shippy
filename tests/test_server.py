"""Tests for the IBP server client."""

import pytest
import requests

from shippy.server import Server, ServerError, to_easypost_address

from .conftest import BASE_URL, SHIPPING_SETTINGS, UNIT, request_address


@pytest.mark.parametrize("base", [BASE_URL, BASE_URL + "/"])
def test_base_url_keeps_api_prefix(http, base):
    """The /api prefix survives with or without a trailing slash."""
    http.add("units", [UNIT])
    assert Server(base).units() == [UNIT]
    assert http.calls == [f"{BASE_URL}/units"]


def test_legacy_request_address(http):
    """Legacy integer labels use the read-only by-request address endpoint."""
    http.add("inmates/by-request/98765/address", request_address())
    assert Server(BASE_URL).request_address(98765)["name"] == "Jane Doe #00012345"


@pytest.mark.parametrize(
    "code, jurisdiction", [("TEX", "Texas"), ("fed", "Federal"), ("Texas", "Texas")]
)
def test_new_request_address(http, code, jurisdiction):
    """New labels pass jurisdiction, inmate ID and request index."""
    path = f"inmates/{jurisdiction}/12345/requests/2/address"
    http.add(path, request_address(request_index=2))
    address = Server(BASE_URL).inmate_request_address(code, 12345, 2)
    assert address["request_index"] == 2
    assert http.calls == [f"{BASE_URL}/{path}"]


def test_unknown_jurisdiction_rejected():
    """An unknown jurisdiction code fails before any HTTP call."""
    with pytest.raises(ValueError):
        Server(BASE_URL).inmate_request_address("CAL", 1, 0)


@pytest.mark.parametrize(
    "status_code, detail",
    [
        (404, "No request found with legacy request_id 98765"),
        (409, "Texas inmate #00012345 is not assigned to a unit; cannot address"),
    ],
)
def test_client_errors_raise_server_error(http, status_code, detail):
    """4xx responses raise ServerError carrying the server's detail message."""
    http.add("inmates/by-request/98765/address", {"detail": detail}, status_code)
    with pytest.raises(ServerError) as excinfo:
        Server(BASE_URL).request_address(98765)
    assert excinfo.value.status_code == status_code
    assert excinfo.value.detail == detail


def test_server_errors_raise_http_error(http):
    """5xx responses are not swallowed as client errors."""
    http.add("units", {"detail": "boom"}, 500)
    with pytest.raises(requests.HTTPError):
        Server(BASE_URL).units()


def test_unit_name_is_url_quoted(http):
    """Unit names with spaces or slashes are quoted into one path segment."""
    http.add("units/Federal/FCI%20Fort%20Worth%2FAdmin", UNIT)
    assert Server(BASE_URL).unit("FED", "FCI Fort Worth/Admin") == UNIT


def test_return_address_from_shipping_settings(http):
    """The return address comes from GET /shipping-settings."""
    http.add("shipping-settings", SHIPPING_SETTINGS)
    assert Server(BASE_URL).return_address() == SHIPPING_SETTINGS["return_address"]


def test_to_easypost_address_blanks_null_street2():
    """A null street2 becomes an empty string for EasyPost."""
    assert to_easypost_address("X", UNIT)["street2"] == ""
