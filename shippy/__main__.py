"""The main application."""

import argparse
import traceback
import functools
import contextlib
import configparser
import pkg_resources

import pyfiglet
from PIL import Image

from . import console
from .misc import grab_png_from_url
from .server import Server, ServerMock
from .printing import print_image
from .shipment import Builder as ShipmentBuilder


def catch_and_print_error(func):
    """Given user an opportunity to see an error before main closes."""

    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            traceback.print_exc()
            print(f"Error: {exc}")
            input("Hit any key to close")

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
    else:
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


def generate_addresses_manual(server):  # pylint: disable=unused-argument
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
def main():  # pylint: disable=too-many-locals, too-many-statements
    """Ship to an inmate or a unit."""
    parser = argparse.ArgumentParser(description=main.__doc__)

    parser.add_argument("--configpath", type=str, default=None)

    subparsers = parser.add_subparsers()
    parsers = [None, None, None]

    parsers[0] = subparsers.add_parser("individual", help="ship individual packages")
    parsers[0].set_defaults(generate_addresses=generate_addresses_individual)

    parsers[1] = subparsers.add_parser("bulk", help="ship bulk packages")
    parsers[1].set_defaults(generate_addresses=generate_addresses_bulk)

    parsers[2] = subparsers.add_parser("manual", help="ship manual packages")
    parsers[2].set_defaults(generate_addresses=generate_addresses_manual)

    args = parser.parse_args()

    try:
        args.generate_addresses
    except AttributeError as error:
        msg = "Shipping type (i.e. bulk, individual, or manual) must be specified"
        raise ValueError(msg) from error

    if args.configpath is not None:
        configpath = args.configpath
    else:
        configpath = pkg_resources.resource_filename(__name__, "config.ini")

    config = configparser.ConfigParser()
    config.read(configpath)

    build_shipment = ShipmentBuilder(config["easypost"]["apikey"])

    if bool(int(config["ibp"]["testing"])):
        server = ServerMock()

    else:
        url, apikey = config["ibp"]["url"], config["ibp"]["apikey"]
        server = Server(url, apikey)

    logofile = config["ibp"].get("logo")  # Logo configuration is optional.
    logopath = logofile and pkg_resources.resource_filename(__name__, logofile)
    logo = logopath and Image.open(logopath)

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
                    shipment.refund()
                raise

        with request_refund_on_error(shipment):
            if ship_shipment is not None:
                with task_message("Registering shipment to IBP server"):
                    ship_shipment(shipment)

            with task_message("Printing postage"):
                label_url = shipment.postage_label.label_url
                image = grab_png_from_url(label_url)

                if logo:
                    # Pasted logo position chosen through trial and error.
                    image.paste(logo, (450, 425))

                print_image(image)


if __name__ == "__main__":
    main()
