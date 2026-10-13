"""Run the application in a CLI."""

import argparse
import collections
import configparser
import contextlib
import datetime
import importlib.resources
import pathlib
import typing

import easypost  # type: ignore
import googlemaps  # type: ignore
import questionary
from PIL import Image

from . import console, shipping
from .misc import grab_png_from_url
from .models import Config
from .printing import print_image, snapshot_printer_state
from .server import Server, ServerError, to_easypost_address


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

    with console.task_message("Grabbing shipping settings from IBP server"):
        recipient_name = server.shipping_settings()["unit_recipient_name"]

    with console.task_message("Grabbing units list from IBP server"):
        units = build_unit_choices(server.units())

    while True:
        unit = console.query_unit(units)
        if unit is None:
            continue

        jurisdiction, name = units[unit]
        try:
            with console.task_message("Grabbing unit address from IBP server"):
                unit_data = server.unit(jurisdiction, name)
        except ServerError as exc:
            questionary.print(f"  {exc.detail}", style="fg:red")
            continue

        to_addr = to_easypost_address(recipient_name, unit_data)

        weight = console.query_weight()
        if weight is None:
            continue

        yield to_addr, weight


STALE_UNIT_AGE = datetime.timedelta(days=90)
"""How old an inmate's unit data can be before shippy warns it may be outdated."""


def fetch_request_address(
    server: Server, request_id: typing.Union[typing.Tuple[str, int, int], int]
) -> dict[str, typing.Any]:
    """Fetch the shipping address for a scanned request label."""
    if isinstance(request_id, tuple):
        # New-style label ID, e.g. "TEX-12345678-0".
        jurisdiction, inmate_id, index = request_id
        return server.inmate_request_address(jurisdiction, inmate_id, index)

    # Legacy label ID: the bare request autoid.
    return server.request_address(request_id)


def unit_is_stale(
    datetime_fetched: typing.Optional[str], now: datetime.datetime
) -> bool:
    """Whether an inmate's unit was last fetched too long ago (or never)."""
    if not datetime_fetched:
        return True

    try:
        fetched = datetime.datetime.fromisoformat(datetime_fetched)
    except ValueError:
        return True

    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=datetime.timezone.utc)

    return now - fetched > STALE_UNIT_AGE


def check_request_address(
    address: dict[str, typing.Any],
    now: typing.Optional[datetime.datetime] = None,
) -> bool:
    """Warn about a request's address; return whether to go ahead and ship.

    A stale unit only warns. A tossed request needs explicit confirmation,
    since it normally should not be shipped at all.
    """
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    questionary.print(
        f"  Shipping to {address['name']} at {address['unit_name']}",
        style="fg:white",
    )

    if unit_is_stale(address.get("datetime_fetched"), now):
        questionary.print(
            "  Warning: this inmate's unit has not been checked in over "
            f"{STALE_UNIT_AGE.days} days and may be out of date.",
            style="fg:yellow",
        )

    if address.get("action") == "Tossed":
        questionary.print(
            "  Warning: this request is marked TOSSED, not filled.",
            style="fg:red bold",
        )
        return console.confirm_tossed()

    return True


def generate_addresses_individual(config: Config):
    """Generate addresses for individual shipping."""
    server = Server.from_config(config.ibp)

    while True:
        request_id = console.query_request_id()
        if request_id is None:
            continue

        try:
            with console.task_message("Grabbing address from IBP server"):
                address = fetch_request_address(server, request_id)
        except ServerError as exc:
            questionary.print(f"  {exc.detail}", style="fg:red")
            continue

        if not check_request_address(address):
            questionary.print("  Skipped; no postage bought.", style="fg:yellow")
            continue

        to_addr = to_easypost_address(address["name"], address)

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

    with console.task_message("Grabbing return address from IBP server"):
        return_address = Server.from_config(config.ibp).return_address()
        from_addr = shipping.build_address(easypost_client, **return_address)

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
