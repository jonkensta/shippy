"""The main application."""

import configparser
import contextlib
import importlib.resources

import easypost
import questionary
from PIL import Image

from . import console, shipping
from .misc import grab_png_from_url
from .printing import print_image
from .server import Server, ServerMock


def generate_addresses_bulk(server: Server, *_):
    """Generate addresses for bulk shipping."""
    with console.task_message("Grabbing units list from IBP server"):
        units = server.unit_ids()

    # Normalize unit names to uppercase.
    units = {key.upper(): value for key, value in units.items()}

    while True:
        unit = console.query_unit(units)
        if unit is None:
            continue

        unit_id = units[unit]
        to_addr = server.unit_address(unit_id)

        weight = console.query_weight()
        if weight is None:
            continue

        def ship_shipment(shipment):
            return server.ship(shipment, unit_autoid=unit_id)

        yield to_addr, weight, ship_shipment


def generate_addresses_individual(server: Server, *_):
    """Generate addresses for individual shipping."""
    while True:
        request_id = console.query_request_id()
        if request_id is None:
            continue

        to_addr = server.request_address(request_id)

        weight = console.query_weight()
        if weight is None:
            continue

        def ship_shipment(shipment):
            return server.ship(shipment, request_ids=[request_id])

        yield to_addr, weight, ship_shipment


def generate_addresses_manual(*_):
    """Generate addresses for manual shipping."""
    while True:
        to_addr = console.query_address()
        if not to_addr:
            continue

        ship_shipment = None

        weight = console.query_weight()
        if weight is None:
            continue

        yield to_addr, weight, ship_shipment


@console.catch_and_print_error
def main(generate_addresses):  # pylint: disable=too-many-locals
    """Ship to an inmate or a unit."""
    configpath = importlib.resources.files(__package__ or __name__).joinpath(
        "config.ini"
    )

    config = configparser.ConfigParser()
    config.read(configpath)

    easypost_api_key = config["easypost"]["apikey"]
    easypost_client = easypost.EasyPostClient(easypost_api_key)

    ibp_testing = bool(int(config["ibp"]["testing"]))
    ibp_url = config["ibp"]["url"]
    ibp_api_key = config["ibp"]["apikey"]
    server = ServerMock() if ibp_testing else Server(ibp_url, ibp_api_key)

    logo = None
    logofile = config["ibp"].get("logo")  # Logo configuration is optional.
    if logofile is not None:
        logopath = importlib.resources.files(__package__ or __name__).joinpath(logofile)
        logo = Image.open(logopath)

    questionary.print(console.WELCOME, style="fg:white")

    with console.task_message("Grabbing return address from IBP server"):
        from_addr_dict = server.return_address()
        from_addr = shipping.build_address(easypost_client, **from_addr_dict)

    try:
        with console.task_message("Verifying return address"):
            easypost_client.address.verify(from_addr.id)
    except easypost.errors.InvalidRequestError:
        pass

    for to_addr_dict, weight, ship_shipment in generate_addresses(server):
        to_addr = shipping.build_address(easypost_client, **to_addr_dict)

        try:
            with console.task_message("Verifying address"):
                easypost_client.address.verify(to_addr.id)
        except easypost.errors.InvalidRequestError:
            pass

        weight = 16.0 * weight  # Convert to ounces.

        with console.task_message("Purchasing postage"):
            shipment = shipping.build_shipment(
                easypost_client, from_addr, to_addr, weight
            )

        @contextlib.contextmanager
        def request_refund_on_error(shipment):
            """Manage a shipment context where a refund is requested on error."""
            try:
                yield shipment
            except Exception:
                with console.task_message("Requesting refund"):
                    easypost_client.shipment.refund(shipment.id)
                raise

        with request_refund_on_error(shipment):
            if ship_shipment is not None:
                with console.task_message("Registering shipment to IBP server"):
                    ship_shipment(shipment)

            with console.task_message("Printing postage"):
                label_url = shipment.postage_label.label_url
                image = grab_png_from_url(label_url)

                if logo is not None:
                    image.paste(logo, (450, 425))

                print_image(image)
