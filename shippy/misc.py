"""Miscellaneous utility functions."""

import os
import tempfile
import contextlib
import urllib.request

from PIL import Image


@contextlib.contextmanager
def build_tempfile(*args, **kwargs):
    """Build a tempfile without opening it."""
    # Create before the try: if NamedTemporaryFile itself fails there is no file
    # to remove, and running the finally anyway raised UnboundLocalError,
    # replacing the real error (bad dir, permissions, disk full) with a
    # confusing one.
    tmp = tempfile.NamedTemporaryFile(*args, **kwargs, delete=False)
    try:
        tmp.close()
        yield tmp
    finally:
        os.remove(tmp.name)


def grab_png_from_url(url: str):
    """Grab a PNG image from a URL."""
    with build_tempfile(suffix=".png") as tmpfile:
        urllib.request.urlretrieve(url, tmpfile.name)
        img = Image.open(tmpfile.name)
        img.load()
        return img
