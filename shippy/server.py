"""IBP server API abstraction."""

import json
from urllib.parse import urljoin

import requests
from easypost.models import Shipment as EasyPostShipment


class ServerABC:
    """Server abstract base class."""

    # pylint: disable=invalid-name, disable=redefined-builtin

    def unit_ids(self) -> list[int]:
        """Get list of unit names with IDs."""
        raise NotImplementedError

    def return_address(self) -> dict[str, str]:
        """Get configured return address."""
        raise NotImplementedError

    def unit_address(self, autoid: int) -> dict[str, str]:
        """Get unit address from its ID."""
        raise NotImplementedError

    def request_address(self, autoid: int) -> dict[str, str]:
        """Get address for a request given its request identifier."""
        raise NotImplementedError

    def ship(
        self,
        shipment: EasyPostShipment,
        request_ids: list[int] = [],
        unit_autoid: int | None = None,
    ):
        """Ship a shipment with optional request autoid."""
        raise NotImplementedError


class Server(ServerABC):
    """Server API convenience class."""

    # pylint: disable=invalid-name, disable=redefined-builtin

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

    def unit_ids(self):
        """Get list of unit names with ids."""
        return self._post("unit_autoids")

    def return_address(self):
        """Get configured return address."""
        return self._post("return_address")

    def unit_address(self, autoid):
        """Get unit address from its id."""
        return self._post(f"unit_address/{autoid:d}")

    def _request_address_autoid(self, autoid):
        """Get address for a request given its autoid."""
        return self._post(f"request_address/{autoid:d}")

    def request_address(self, autoid):
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


class ServerMock(ServerABC):
    """Server class for testing."""

    # pylint: disable=invalid-name, unused-argument

    def unit_ids(self):
        """Get list of unit names with IDs."""
        return {
            "ALFRED HUGHES": 68,
            "ALLRED": 19,
            "B MOORE": 94,
            "BARTLETT": 20,
            "BAS": 1,
            "BATEN": 76,
            "BETO": 21,
            "BIG": 6,
            "BILL CLEMENTS": 29,
            "BML": 2,
            "BMM": 3,
            "BMP": 4,
            "BOYD": 22,
            "BRADSHAW": 23,
            "BRIDGEPORT": 24,
            "BRIDGEPORT PPT": 25,
            "BRY": 7,
            "BSC": 5,
            "BYRD": 27,
            "C MOORE": 95,
            "CAROL YOUNG COMPLEX": 136,
            "CHASE FIELD W6": 51,
            "CHRISTINA MELTON CRAIN UNIT": 35,
            "CLEMENS": 28,
            "CLEVELAND": 30,
            "COFFIELD": 31,
            "COLE": 32,
            "CONNALLY": 33,
            "COTULLA": 34,
            "CRW": 8,
            "DAL": 10,
            "DALHART": 36,
            "DANIEL": 37,
            "DARRINGTON": 38,
            "DIBOLL PRIV": 39,
            "DOLPH BRISCOE": 26,
            "DOMINGUEZ": 40,
            "DUNCAN": 41,
            "EAST TEXAS TREATMENT FACILITY": 42,
            "EASTHAM": 43,
            "EDN": 9,
            "ELLIS": 44,
            "ESTELLE": 45,
            "FERGUSON": 47,
            "FORMBY": 48,
            "FORT STOCKTON": 49,
            "FTW": 137,
            "GARZA EAST": 138,
            "GARZA WEST": 52,
            "GIB LEWIS": 80,
            "GIST": 53,
            "GLOSSBRENNER": 54,
            "GOODMAN": 55,
            "GOREE": 56,
            "HALBERT": 58,
            "HAMILTON": 59,
            "HENLEY": 61,
            "HIGHTOWER": 62,
            "HILLTOP": 63,
            "HOBBY": 64,
            "HODGE": 65,
            "HOLLIDAY": 66,
            "HOSPITAL-GALV": 67,
            "HOU": 11,
            "HUNTSVILLE": 69,
            "HUTCHINS": 70,
            "J MIDDLETON": 91,
            "JAMES LYNAUGH": 87,
            "JESTER I": 71,
            "JESTER III": 72,
            "JESTER IV": 73,
            "JOE F GURNEY": 57,
            "JOHNSTON": 74,
            "JORDAN": 75,
            "KEGANS STATE J": 77,
            "KYLE": 78,
            "LAT": 13,
            "LEBLANC": 79,
            "LINDSEY SJ": 81,
            "LOCKHART PRIV P": 82,
            "LOCKHART WORK FAC": 83,
            "LOPEZ": 84,
            "LUTHER": 85,
            "LYCHNER": 86,
            "MAC STRINGFELLOW": 121,
            "MARLIN": 88,
            "MCCONNELL": 89,
            "MICHAEL": 90,
            "MONTFORD": 92,
            "MOUNTAIN VIEW": 96,
            "MURRAY": 97,
            "NEAL": 98,
            "NEY": 99,
            "PACK I": 100,
            "PLANE JAIL": 101,
            "POLUNSKY": 103,
            "POWLEDGE": 104,
            "RAMSEY I": 105,
            "REE": 14,
            "ROACH": 106,
            "ROACH BT CAMP": 108,
            "ROACH WRK CMP": 107,
            "ROBERTSON": 109,
            "RUDD": 110,
            "RVS": 15,
            "SAN SABA": 111,
            "SANCHEZ": 112,
            "SANDERS ESTES": 46,
            "SANTA MARIA BABY BONDING": 102,
            "SAYLE": 113,
            "SEA": 16,
            "SEGOVIA": 115,
            "SKYVIEW": 116,
            "SMITH": 117,
            "SOUTH TEXAS ISF": 118,
            "STEVENSON": 119,
            "STILES": 120,
            "TELFORD": 122,
            "TERRELL": 123,
            "TEX": 17,
            "THOMAS HAVINS": 60,
            "TORRES": 124,
            "TRAVIS JAIL": 125,
            "TRV": 18,
            "TULIA": 126,
            "VANCE": 127,
            "WALLACE": 128,
            "WARE": 130,
            "WAYNE SCOTT": 114,
            "WEST TEXAS HOSP": 93,
            "WEST TEXAS ISF": 131,
            "WHEELER": 132,
            "WILDERNESS 3": 129,
            "WILLACY": 133,
            "WOODMAN SJ": 134,
            "WYNNE": 135,
        }

    def return_address(self):
        """Get configured return address."""
        return {
            "name": "Inside Books Project",
            "city": "Austin",
            "state": "Texas",
            "street1": "827 West 12th St",
            "street2": "",
            "zipcode": "78701",
        }

    def unit_address(self, *args, **kwargs):
        """Get unit address from unit ID."""
        return {
            "city": "Colorado City",
            "name": "ATTN: Mailroom Staff",
            "state": "TX",
            "street1": "San Angelo Work Camp",
            "street2": "1675 S. FM 3525",
            "zipcode": "79512",
        }

    def request_address(self, *args, **kwargs):
        """Get address for a request given its request identifier."""
        return {
            "city": "Tennessee Colony",
            "name": "Timothy Louis #00268601",
            "state": "TX",
            "street1": "Coffield Unit",
            "street2": "2661 FM 2054",
            "zipcode": "75884",
        }

    def ship(self, *args, **kwargs):
        """Ship a shipment with optional request autoid."""
