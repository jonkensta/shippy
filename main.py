"""
The main application.
"""

import argparse
import traceback
import functools
import contextlib
import configparser
import pkg_resources

from PIL import Image

from shippy import console
from shippy.misc import grab_png_from_url
from shippy.server import Server, ServerMock
from shippy.printing import print_image
from shippy.shipment import Builder as ShipmentBuilder


def catch_and_print_error(func):
    """Given user an opportunity to see an error before main closes"""

    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            traceback.print_exc()
            print(f"Error: {exc}")
            input("Hit any key to close")

    return inner


@catch_and_print_error
def main():  # pylint: disable=too-many-locals, too-many-statements
    """Ship to an inmate or a unit"""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--configpath', type=str, default=None)

    subparsers = parser.add_subparsers()
    parsers = [None, None]

    parsers[0] = subparsers.add_parser(
        'individual', help="ship individual packages"
    )
    parsers[0].set_defaults(ship_bulk=False)

    parsers[1] = subparsers.add_parser(
        'bulk', help="ship bulk packages"
    )
    parsers[1].set_defaults(ship_bulk=True)

    args = parser.parse_args()

    try:
        args.ship_bulk
    except AttributeError as error:
        msg = "Shipping type (i.e. bulk or individual) must be specified"
        raise ValueError(msg) from error

    if args.configpath is not None:
        configpath = args.configpath
    else:
        configpath = pkg_resources.resource_filename(__name__, 'config.ini')

    config = configparser.ConfigParser()
    config.read(configpath)

    build_shipment = ShipmentBuilder(config['easypost']['apikey'])

    if bool(int(config['ibp']['testing'])):
        server = ServerMock()

    else:
        url, apikey = config['ibp']['url'], config['ibp']['apikey']
        server = Server(url, apikey)

    logo = Image.open(config['ibp']['logo'])

    @contextlib.contextmanager
    def task_message(msg):
        try:
            print(msg, '...', '', end='', flush=True)
            yield
        except Exception:
            print("error!", flush=True)
            raise
        else:
            print("done!", flush=True)

    with task_message("Grabbing return address from IBP server"):
        from_addr = server.return_address()
        from_addr['name'] = from_addr.pop('addressee')

    if args.ship_bulk:
        with task_message("Grabbing units list from IBP server"):
            units = server.unit_autoids()

    while True:

        if args.ship_bulk:
            request_ids = []
            unit = console.query_unit(units)
            unit_autoid = units[unit]
            to_addr = server.unit_address(unit_autoid)

        else:
            request_id = console.query_request_id()
            request_ids = [request_id]

            unit_autoid = None
            to_addr = server.request_address(request_id)

        weight = console.query_weight()

        with task_message("Purchasing postage"):
            shipment = build_shipment(from_addr, to_addr, weight)

        try:
            with task_message("Registering shipment to IBP server"):
                server.ship_requests(request_ids, shipment, unit_autoid)

            with task_message("Printing postage"):
                label_url = shipment.postage_label.label_url
                image = grab_png_from_url(label_url)

                # Pasted logo position chosen through trial and error.
                image.paste(logo, (450, 425))

                print_image(image)

        except Exception:
            with task_message("Requesting refund"):
                shipment.refund()
            raise


if __name__ == '__main__':
    main()
