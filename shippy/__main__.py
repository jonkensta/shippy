"""
The main application.
"""

import argparse
import traceback
import contextlib
import configparser
import pkg_resources

from . import console
from .server import Server, ServerMock
from .misc import grab_png_from_url, print_image
from .shipment import Builder as ShipmentBuilder


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
                print_image(image)

        except Exception:
            with task_message("Requesting refund"):
                shipment.refund()
            raise


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error: {exc}")
        traceback.print_exc()
        input("Hit any key to close")
