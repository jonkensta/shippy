"""The main entrypoint to the shippy."""

import argparse

from .base import (
    generate_addresses_bulk,
    generate_addresses_individual,
    generate_addresses_manual,
)
from .base import main as run_main


def main():
    """Ship bulk or individual IBP packages."""
    parser = argparse.ArgumentParser(description=main.__doc__)

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

    run_main(args.generate_addresses)


if __name__ == "__main__":
    main()
