"""Printing implementation for different systems."""

import sys

if sys.platform == "win32":
    from .windows import print_image, snapshot_printer_state  # pylint: disable=unused-import
else:
    from .linux import print_image, snapshot_printer_state  # pylint: disable=unused-import
