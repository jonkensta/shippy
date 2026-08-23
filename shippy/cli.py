"""Run the application in a CLI."""

import argparse
import collections
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
from .printing import print_image, snapshot_printer_state
from .server import Server


def build_unit_choices(units: list[dict]) -> dict[str, tuple[str, str]]:
    """Map uppercased display names to (jurisdiction, name) unit keys.

    Unit names are only unique per jurisdiction, so the jurisdiction is
    appended to the display name whenever a name is shared across
    jurisdictions.
    """
    name_counts = collections.Counter(unit["name"].upper() for unit in units)

    choices = {}
    for unit in units:
        key = unit["name"].upper()
        if name_counts[key] > 1:
            key = f"{key} ({unit['jurisdiction'].upper()})"
        choices[key] = (unit["jurisdiction"], unit["name"])

    return choices


def generate_addresses_bulk(config: Config):
    """Generate addresses for bulk shipping."""
    server = Server.from_config(config.ibp)

    with console.task_message("Grabbing units list from IBP server"):
        units = build_unit_choices(server.units())

    while True:
        unit = console.query_unit(units)
        if unit is None:
            continue

        jurisdiction, name = units[unit]
        to_addr = server.unit_address(jurisdiction, name)

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

        if isinstance(request_id, tuple):
            # New-style label ID, e.g. "TEX-12345678-0".
            jurisdiction, inmate_id, _index = request_id
            to_addr = server.inmate_address(jurisdiction, inmate_id)
        else:
            # Legacy label ID: the bare request autoid.
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


def run_diagnose_printer(_args):
    """Print a snapshot of printer/USB state to help debug detection failures."""
    print(snapshot_printer_state())


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

    parser.add_argument("--config", type=pathlib.Path, help="Configuration file path")

    subparsers = parser.add_subparsers(
        dest="shipping_type", required=True, help="Select command"
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

    subparsers.add_parser(
        "diagnose-printer",
        help="print a snapshot of printer/USB state (no config needed)",
    ).set_defaults(func=run_diagnose_printer)

    return parser


def main():
    """Ship to an inmate or a unit."""

    parser = build_parser()
    args = parser.parse_args()

    # Utility subcommands (e.g. diagnose-printer) run without config and exit.
    if getattr(args, "func", None) is not None:
        args.func(args)
        return

    if args.config is None:
        parser.error("--config is required for shipping commands")

    config = load_config(args.config)

    easypost_client = easypost.EasyPostClient(config.easypost.apikey)

    logo = load_logo()

    questionary.print(console.WELCOME, style="fg:white")
    questionary.print(
        "\nWelcome! Answer prompts to print postage, hit CTRL+C to cancel and restart\n"
    )

    with console.task_message("Building return address from config"):
        from_addr = shipping.build_address(
            easypost_client, **config.return_address.model_dump()
        )

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
                easypost_client, from_addr, to_addr, weight, config.parcel
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
            try:
                with console.task_message("Printing postage"):
                    label_url = shipment.postage_label.label_url
                    image = grab_png_from_url(label_url)

                    if logo is not None:
                        image.paste(logo, (450, 425))

                    print_image(image)
            except RuntimeError as exc:
                questionary.print(f"  Error: {exc}", style="fg:red")
                raise
