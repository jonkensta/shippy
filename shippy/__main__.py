"""The main application."""

import argparse
import configparser
import contextlib
import functools
import importlib.resources
import traceback

import pyfiglet
from PIL import Image

from . import console
from .misc import grab_png_from_url
from .printing import print_image
from .server import Server, ServerMock
from .shipment import Builder as ShipmentBuilder


def catch_and_print_error(func):
    """Given user an opportunity to see an error before main closes."""

    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            traceback.print_exc()
            print(f"Error: {exc}")
            input("Hit any key to close")
            raise

    return inner


@contextlib.contextmanager
def task_message(msg):
    """Capture a task context with messaging."""
    try:
        print(msg, "...", "", end="", flush=True)
        yield
    except Exception:
        print("error!", flush=True)
        raise

    print("done!", flush=True)


def generate_addresses_bulk(server):
    """Generate addresses for bulk shipping."""
    with task_message("Grabbing units list from IBP server"):
        units = server.unit_ids()

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
            return server.ship_bulk(unit_id, shipment)

        yield to_addr, weight, ship_shipment


def generate_addresses_individual(server):
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
            return server.ship_request(request_id, shipment)

        yield to_addr, weight, ship_shipment


def generate_addresses_manual(_):
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


@catch_and_print_error
def main():  # pylint: disable=too-many-locals
    """Ship to an inmate or a unit."""
    parser = argparse.ArgumentParser(description=main.__doc__)

    parser.add_argument(
        "--configpath",
        type=str,
        default=None,
        help="Explicit path to the configuration file.",
    )

    subparsers = parser.add_subparsers(
        dest="shipping_type", required=True, help="Select shipping type"
    )

    subparsers.add_parser("individual", help="ship individual packages").set_defaults(
        generate_addresses=generate_addresses_individual
    )

    subparsers.add_parser("bulk", help="ship bulk packages").set_defaults(
        generate_addresses=generate_addresses_bulk
    )

    subparsers.add_parser("manual", help="ship manual packages").set_defaults(
        generate_addresses=generate_addresses_manual
    )

    args = parser.parse_args()

    default_configpath = importlib.resources.files(__package__ or __name__).joinpath(
        "config.ini"
    )

    configpath = args.configpath if args.configpath is not None else default_configpath

    config = configparser.ConfigParser()
    config.read(configpath)

    easypost_api_key = config["easypost"]["apikey"]
    build_shipment = ShipmentBuilder(easypost_api_key)

    ibp_testing = bool(int(config["ibp"]["testing"]))
    ibp_url = config["ibp"]["url"]
    ibp_api_key = config["ibp"]["apikey"]
    server = ServerMock() if ibp_testing else Server(ibp_url, ibp_api_key)

    logo = None
    logofile = config["ibp"].get("logo")  # Logo configuration is optional.
    if logofile is not None:
        logopath = importlib.resources.files(__package__ or __name__).joinpath(logofile)
        logo = Image.open(logopath)

    welcome = pyfiglet.Figlet(font="slant").renderText("IBP Shipping")
    print(welcome)

    with task_message("Grabbing return address from IBP server"):
        from_addr = server.return_address()

    for to_addr, weight, ship_shipment in args.generate_addresses(server):

        with task_message("Purchasing postage"):
            shipment = build_shipment(from_addr, to_addr, weight)

        @contextlib.contextmanager
        def request_refund_on_error(shipment):
            """Manage a shipment context where a refund is requested on error."""
            try:
                yield shipment
            except Exception:
                with task_message("Requesting refund"):
                    build_shipment._client.shipment.refund(shipment.id)
                raise

        with request_refund_on_error(shipment):
            if ship_shipment is not None:
                with task_message("Registering shipment to IBP server"):
                    ship_shipment(shipment)

            with task_message("Printing postage"):
                label_url = shipment.postage_label.label_url
                image = grab_png_from_url(label_url)

                if logo is not None:
                    image.paste(logo, (450, 425))

                print_image(image)


if __name__ == "__main__":
    main()
