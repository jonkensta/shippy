"""
Miscellaneous utility functions.
"""

import os
import tempfile
import contextlib
import urllib.request

import win32ui
import win32print

from PIL import Image, ImageWin


def grab_png_from_url(url: str):
    """Grab a PNG image from a URL"""

    @contextlib.contextmanager
    def build_tempfile(*args, **kwargs):
        """Build a tempfile without opening it"""
        try:
            tmp = tempfile.NamedTemporaryFile(*args, **kwargs, delete=False)
            tmp.close()
            yield tmp
        finally:
            os.remove(tmp.name)

    with build_tempfile(suffix='.png') as tmpfile:
        urllib.request.urlretrieve(url, tmpfile.name)
        return Image.open(tmpfile.name)


def print_image(img, printer=win32print.GetDefaultPrinter()):
    """Print a given image."""
    # pylint: disable=too-many-locals, too-many-statements

    @contextlib.contextmanager
    def create_printer_context(printer_name):
        try:
            context = win32ui.CreateDC()
            context.CreatePrinterDC(printer_name)
            yield context

        finally:
            context.DeleteDC()

    with create_printer_context(printer) as context:

        def get_printable_area():
            """Get the printable area of a printer from its context"""

            horzres = 8
            horz = context.GetDeviceCaps(horzres)

            vertres = 10
            vert = context.GetDeviceCaps(vertres)

            return horz, vert

        def get_total_area():
            """Get the total area of a printer from its context"""

            physicalwidth = 110
            width = context.GetDeviceCaps(physicalwidth)

            physicalheight = 111
            height = context.GetDeviceCaps(physicalheight)

            return width, height

        @contextlib.contextmanager
        def create_job(name):
            """Start the print job"""

            try:
                context.StartDoc(name)
                context.StartPage()
                yield

            finally:
                context.EndPage()
                context.EndDoc()

        if img.size[0] > img.size[1]:
            img = img.rotate(90)

        printable_w, printable_h = get_printable_area()
        ratios = [printable_w / img.size[0], printable_h / img.size[1]]
        scale = min(ratios)

        # Start the print job, and draw the bitmap to
        #  the printer device at the scaled size.
        with create_job('postage_label'):
            dib = ImageWin.Dib(img)

            total_w, total_h = get_total_area()
            scaled_w, scaled_h = [int(scale * i) for i in img.size]
            lhs_x = int((total_w - scaled_w) / 2)
            lhs_y = int((total_h - scaled_h) / 2)

            rhs_x = lhs_x + scaled_w
            rhs_y = lhs_y + scaled_h

            dib.draw(context.GetHandleOutput(), (lhs_x, lhs_y, rhs_x, rhs_y))
