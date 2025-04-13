"""Run the IBP bulk shipping application."""

import pathlib
import sys

SCRIPT_PATH = pathlib.Path(__file__).resolve()
SCRIPTS_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = SCRIPTS_DIR.parent
PROJECT_ROOT_STR = str(PROJECT_ROOT)
if PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_STR)

# pylint: disable=wrong-import-position, import-error
from shippy.base import generate_addresses_bulk as generate_addresses
from shippy.base import main

if __name__ == "__main__":
    main(generate_addresses)
