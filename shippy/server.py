"""
IBP server API abstraction.
"""

from urllib.parse import urljoin
from typing import List, Dict, Union, Tuple

import requests

from .shipment import extract_data as extract_shipment_data


class ServerABC:
    """Server abstract base class."""

    # pylint: disable=invalid-name, disable=redefined-builtin

    def unit_autoids(self) -> List[int]:
        """Get list of unit names with autoids."""
        raise NotImplementedError

    def return_address(self) -> Dict[str, str]:
        """Get configured return address."""
        raise NotImplementedError

    def unit_address(self, id: int) -> Dict[str, str]:
        """Get unit address from its autoid."""
        raise NotImplementedError

    RequestID = Union[Tuple[str, int, int], int]

    def request_address(self, request_id: RequestID) -> Dict[str, str]:
        """Get address for a request given its request identifier."""
        raise NotImplementedError

    def ship_request(self, request_id: RequestID, shipment):
        """Ship a request given its identifier."""
        raise NotImplementedError

    def ship_bulk(self, id: int, shipment) -> None:
        """Ship a bulk package to a unit given the unit autoid."""
        raise NotImplementedError


class Server(ServerABC):
    """Server API convenience class."""

    # pylint: disable=invalid-name, disable=redefined-builtin

    def __init__(self, url, apikey):
        """Create server API convenience class from url and apikey."""
        self._url = url
        self._apikey = apikey

    def _method(self, method, path, **kwargs):
        url = urljoin(self._url, path)
        response = method(url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _post(self, path, **kwargs):
        return self._method(requests.post, path, **kwargs)

    def _get(self, path, **kwargs):
        return self._method(requests.get, path, **kwargs)

    def _put(self, path, **kwargs):
        return self._method(requests.put, path, **kwargs)

    def unit_autoids(self):
        """Get list of unit names with autoids."""
        units = self._get("units")["units"]
        return {unit["name"]: unit["id"] for unit in units}

    def return_address(self):
        """Get configured return address."""
        config = self._get("config")
        return config["address"]

    def unit_address(self, id):
        """Get unit address from its autoid."""
        return self._get(f"unit/{id:d}/address")

    def _request_address_newid(self, jurisdiction, id, index):
        """Get address for a request given its (jurisdiction, id, index) identifier."""
        return self._get(f"request/{jurisdiction}/{id:d}/{index:d}/address")

    def _request_address_autoid(self, autoid):
        """Get address for a request given its autoid."""
        return self._get(f"request/{autoid:d}/address")

    def request_address(self, request_id):
        """Get address for a request given its request identifier."""
        try:
            request_id = int(request_id)
        except ValueError:
            jurisdiction, id, index = request_id
            return self._request_address_newid(jurisdiction, int(id), int(index))
        else:
            return self._request_address_autoid(request_id)

    def _ship_request_newid(self, jurisdiction, id, index, shipment):
        """Ship a request given its (jurisdiction, id, index) identifier."""
        json = extract_shipment_data(shipment)
        return self._post(f"request/{jurisdiction}/{id:d}/{index:d}/ship", json=json)

    def _ship_request_autoid(self, autoid, shipment):
        """Ship a request given its autoid."""
        json = extract_shipment_data(shipment)
        return self._post(f"request/{autoid:d}/ship", json=json)

    def ship_request(self, request_id, shipment):
        """Ship a request given its identifier."""
        try:
            request_id = int(request_id)
        except ValueError:
            jurisdiction, id, index = request_id
            return self._ship_request_newid(jurisdiction, int(id), int(index), shipment)
        else:
            return self._ship_request_autoid(request_id, shipment)

    def ship_bulk(self, id, shipment):
        """Ship a bulk package to a unit given unit autoid."""
        json = extract_shipment_data(shipment)
        return self._post(f"unit/{id:d}/ship", json=json)


class ServerMock(ServerABC):
    """Server class for testing."""

    def unit_autoids(self):
        """Get list of unit names with autoids."""
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
            "addressee": "Inside Books Project",
            "city": "Austin",
            "state": "Texas",
            "street1": "827 West 12th St",
            "street2": "",
            "zipcode": "78701",
        }

    def unit_address(self, unit_id):
        """Get unit address from unit autoid."""
        return {
            "city": "Colorado City",
            "name": "ATTN: Mailroom Staff",
            "state": "TX",
            "street1": "San Angelo Work Camp",
            "street2": "1675 S. FM 3525",
            "zipcode": "79512",
        }

    def request_address(self, request_id):
        """Get address for a request given its request identifier."""
        return {
            "city": "Tennessee Colony",
            "name": "Timothy Louis #00268601",
            "state": "TX",
            "street1": "Coffield Unit",
            "street2": "2661 FM 2054",
            "zipcode": "75884",
        }

    def ship_request(self, request_id, shipment):
        """Ship a request given its identifier."""

    def ship_bulk(self, unit_autoid, shipment):
        """Ship a bulk package to a unit given unit autoid."""
