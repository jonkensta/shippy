"""
Miscellaneous utility functions.
"""

import os
import io
import tempfile
import subprocess
import urllib.request


def grab_png_from_url(url: str):
    """Grab a PNG image from a URL"""
    with tempfile.NamedTemporaryFile(suffix='.png') as tmpfile:
        urllib.request.urlretrieve(url, tmpfile.name)
        with open(tmpfile.name, 'rb') as imgfile:
            return io.BytesIO(imgfile.read())


def _show_image_posix(filename: str):
    """Show an image on a posix system"""
    subprocess.check_call(['xdg-open', filename])


def _show_image_nt(filename: str):
    """Show an image on an NT system"""
    subprocess.check_call(['powershell', '-c', filename])


def show_image(img):
    """Show an image regardless of running OS"""

    viewers = {'posix': _show_image_posix, 'nt': _show_image_nt}
    with tempfile.NamedTemporaryFile(suffix='.png') as tmpfile:
        with open(tmpfile.name, 'wb') as imgfile:
            imgfile.write(img.getbuffer())
        viewers[os.name](tmpfile.name)
