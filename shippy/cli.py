"""Run the application in a CLI."""

import argparse
import configparser
import contextlib
import importlib.resources
import os
import pathlib
import subprocess
import sys

import easypost  # type: ignore
import googlemaps  # type: ignore
import questionary
from ibp_printing import (
    PrintResult,
    configure_logging,
    discover,
    get_backend,
    print_to_first_available,
)
from ibp_printing.diagnostics import build_report
from PIL import Image

from . import console, shipping
from .misc import build_tempfile, grab_png_from_url
from .models import Config
from .server import Server

# How long to follow a spooled label job before giving up on knowing its outcome.
PRINT_TRACK_TIMEOUT_S = 30.0


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


def run_diagnose_printer(_args):
    """Print a snapshot of printer/USB state to help debug detection failures."""
    log_dir = configure_logging(console=False)
    print(
        build_report(discover(), get_backend().recent_print_events(), log_dir=log_dir)
    )


def preview_image(img: Image.Image) -> None:
    """Open an image in the system viewer instead of printing it (dev use)."""
    with build_tempfile(suffix=".png") as tmpfile:
        img.save(tmpfile.name)
        if sys.platform == "win32":
            os.startfile(tmpfile.name)  # pylint: disable=no-member
        else:
            subprocess.check_call(["xdg-open", tmpfile.name])
        # Keep the temp file alive until the viewer has had a chance to open it.
        input("(preview) press Enter to continue ... ")


def warn_if_job_not_ok(result: PrintResult, log_dir: pathlib.Path) -> None:
    """Tell the volunteer when the spooler could not confirm the label printed."""
    if result.outcome.ok:
        return
    questionary.print(
        f"  Warning: the label was sent to {result.printer_name!r}, but the printer "
        f"queue reported '{result.outcome.value}'. It may NOT have printed.\n"
        "  Check the printer. Postage was already bought and was NOT refunded; if no "
        f"label came out, reprint or refund '{result.job_name}' from EasyPost.\n"
        f"  Printer logs: {log_dir}",
        style="fg:yellow",
    )


def print_postage(
    shipment, logo: Image.Image | None, log_dir: pathlib.Path, *, preview: bool
) -> PrintResult | None:
    """Download the label, stamp the logo and print it (or preview it).

    Raises:
        RuntimeError: (incl. ibp_printing.PrintError) if the label could not be
            sent to any printer; the caller refunds the postage.
    """
    try:
        with console.task_message("Printing postage"):
            image = grab_png_from_url(shipment.postage_label.label_url)

            if logo is not None:
                image.paste(logo, (450, 425))

            if preview:
                preview_image(image)
                return None

            return print_to_first_available(
                image,
                job_name=f"Shipping Label {shipment.id}",
                track_timeout_s=PRINT_TRACK_TIMEOUT_S,
            )
    except RuntimeError as exc:
        questionary.print(f"  Error: {exc}", style="fg:red")
        questionary.print(f"  Printer logs: {log_dir}", style="fg:red")
        raise


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
    parser.add_argument(
        "--preview",
        action="store_true",
        help="open labels in an image viewer instead of printing them (development)",
    )

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
    log_dir = configure_logging(console=False)

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
            result = print_postage(shipment, logo, log_dir, preview=args.preview)

        # Outside the refund context: the job was spooled, so the label may well
        # have printed. Refunding here could leave a printed label with no postage.
        if result is not None:
            warn_if_job_not_ok(result, log_dir)
