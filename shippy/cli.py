"""Run the application in a CLI."""

import argparse
import configparser
import contextlib
import importlib.resources
import pathlib

import easypost  # type: ignore
import googlemaps  # type: ignore
import questionary
from PIL import Image

from . import console, shipping
from .misc import grab_png_from_url
from .models import Config
from .printing import print_image
from .server import Server


def generate_addresses_bulk(config: Config):
    """Generate addresses for bulk shipping."""
    server = Server.from_config(config.ibp)

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

        yield to_addr, weight


def generate_addresses_individual(config: Config):
    """Generate addresses for individual shipping."""
    server = Server.from_config(config.ibp)

    while True:
        request_id = console.query_request_id()
        if request_id is None:
            continue

        to_addr = server.request_address(request_id)

        weight = console.query_weight()
        if weight is None:
            continue

        yield to_addr, weight


def generate_addresses_manual(config: Config):
    """Generate addresses for manual shipping."""
    gmaps = googlemaps.Client(key=config.googlemaps.apikey)

    while True:
        to_addr = console.query_address(gmaps)
        if not to_addr:
            continue

        weight = console.query_weight()
        if weight is None:
            continue

        yield to_addr, weight


def load_logo() -> Image.Image:
    """Load logo image."""
    logo_fpath = importlib.resources.files("shippy.assets").joinpath("logo.jpg")
    return Image.open(str(logo_fpath))


def load_config(filepath: pathlib.Path) -> Config:
    """Load and validate the config file."""
    parser = configparser.ConfigParser()
    parser.read(filepath)

    config_dict = {
        section: dict(parser.items(section)) for section in parser.sections()
    }
    config = Config.model_validate(config_dict)

    return config


def build_parser() -> argparse.ArgumentParser:
    """Build an arguments parser."""
    parser = argparse.ArgumentParser(description=main.__doc__)

    parser.add_argument(
        "--config", type=pathlib.Path, required=True, help="Configuration file path"
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

    return parser


def main():
    """Ship to an inmate or a unit."""

    args = build_parser().parse_args()
    config = load_config(args.config)

    easypost_client = easypost.EasyPostClient(config.easypost.apikey)
    server = Server.from_config(config.ibp)

    logo = load_logo()

    questionary.print(console.WELCOME, style="fg:white")
    questionary.print(
        "\nWelcome! Answer prompts to print postage, hit CTRL+C to cancel and restart\n"
    )

    with console.task_message("Grabbing return address from IBP server"):
        from_addr = shipping.build_address(easypost_client, **server.return_address())

    try:
        with console.task_message("Verifying return address"):
            easypost_client.address.verify(from_addr.id)
    except easypost.errors.InvalidRequestError:
        questionary.print(
            "  Failed to verify return address, consider double-checking before shipping.",
            style="fg:yellow",
        )

    for to_addr_dict, weight in args.generate_addresses(config):
        to_addr = shipping.build_address(easypost_client, **to_addr_dict)

        try:
            with console.task_message("Verifying address"):
                easypost_client.address.verify(to_addr.id)
        except easypost.errors.InvalidRequestError:
            questionary.print(
                "  Failed to verify address, consider double-checking before shipping.",
                style="fg:yellow",
            )

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
            with console.task_message("Printing postage"):
                label_url = shipment.postage_label.label_url
                image = grab_png_from_url(label_url)

                if logo is not None:
                    image.paste(logo, (450, 425))

                print_image(image)
