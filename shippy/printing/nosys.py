"""
Printing on a system that doesn't have a printer.
"""

import os
import subprocess

from ..misc import build_tempfile


def _show_image_posix(filename: str):
    """Show an image on a posix system"""
    subprocess.check_call(['xdg-open', filename])


def _show_image_nt(filename: str):
    """Show an image on an NT system"""
    subprocess.check_call(['powershell', '-c', filename])


def print_image(img, **kwargs):  # pylint: disable=unused-argument
    """Show an image regardless of running OS"""

    viewers = {'posix': _show_image_posix, 'nt': _show_image_nt}
    with build_tempfile(suffix='.png') as tmpfile:
        img.save(tmpfile.name)
        viewers[os.name](tmpfile.name)
