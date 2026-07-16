"""Printing on a system that doesn't have a printer."""

import subprocess

from ..misc import build_tempfile


def print_image(img):
    """Show an image using `xdg-open`."""
    with build_tempfile(suffix=".png") as tmpfile:
        img.save(tmpfile.name)
        subprocess.check_call(["xdg-open", tmpfile.name])


def snapshot_printer_state():
    """The USB label-printer detection path only runs on Windows."""
    return (
        "shippy printer diagnostics are only available on the Windows shipping "
        "machine; this platform uses a fallback image viewer for printing."
    )
