"""Printing on win32 platform."""

import contextlib
import subprocess

from ..misc import build_tempfile

try:
    import win32print  # pylint: disable=import-error
    import win32ui  # pylint: disable=import-error
    import wmi  # type: ignore
    from PIL import ImageWin
except ImportError:
    HAS_PYWIN32 = False
else:
    HAS_PYWIN32 = True


if HAS_PYWIN32:

    def get_available_usb_printers():
        """Get iterable of available USB printers."""

        @contextlib.contextmanager
        def open_printer(name: str):
            """Handle printer context."""
            try:
                handle = win32print.OpenPrinter(name)
                yield handle
            finally:
                win32print.ClosePrinter(handle)

        def get_local_printers():
            """Get iterable of local printers."""
            for printer_info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
                printer_name = printer_info[2]
                yield printer_name

        def is_usb_printer(name: str) -> bool:
            """Flag if printer is a USB printer."""
            with open_printer(name) as handle:
                details = win32print.GetPrinter(handle, 2)
                return "USB" in details.get("pPortName", "").upper()

        def is_available_printer(name: str) -> bool:
            """Flag if printer is has a corresponding PNP entity."""
            entities = wmi.WMI().query(
                "SELECT * from Win32_PnPEntity "
                f"WHERE Name = '{name}' AND PNPDeviceID LIKE 'USBPRINT%'"
            )
            return len(entities) > 0

        printers = get_local_printers()
        printers = filter(is_usb_printer, printers)
        printers = filter(is_available_printer, printers)
        yield from printers

    def print_image(img):  # pylint: disable=too-many-locals
        """Print a given image."""

        printer = next(get_available_usb_printers(), win32print.GetDefaultPrinter())

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
                """Get the printable area of a printer from its context."""

                horzres = 8
                horz = context.GetDeviceCaps(horzres)

                vertres = 10
                vert = context.GetDeviceCaps(vertres)

                return horz, vert

            def get_total_area():
                """Get the total area of a printer from its context."""

                physicalwidth = 110
                width = context.GetDeviceCaps(physicalwidth)

                physicalheight = 111
                height = context.GetDeviceCaps(physicalheight)

                return width, height

            @contextlib.contextmanager
            def create_job(name):
                """Start the print job."""

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
            backoff = (
                0.95  # Backoff error empirically added to avoid chopping the page.
            )
            scale = backoff * min(ratios)

            # Start print job, draw the bitmap to printer at scaled size.
            with create_job("postage_label"):
                dib = ImageWin.Dib(img)

                total_w, total_h = get_total_area()
                scaled_w, scaled_h = [int(scale * i) for i in img.size]
                lhs_x = int((total_w - scaled_w) / 2)
                lhs_y = int((total_h - scaled_h) / 2)

                rhs_x = lhs_x + scaled_w
                rhs_y = lhs_y + scaled_h

                dib.draw(context.GetHandleOutput(), (lhs_x, lhs_y, rhs_x, rhs_y))

else:

    def print_image(img):  # pylint: disable=unused-argument
        """Show an image using `powershell`."""
        with build_tempfile(suffix=".png") as tmpfile:
            img.save(tmpfile.name)
            subprocess.check_call(["powershell", "-c", tmpfile.name])
