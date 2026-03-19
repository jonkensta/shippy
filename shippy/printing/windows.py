"""Printing on win32 platform."""

import contextlib
import re
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

    _VID_PID_RE = re.compile(r"[\s\-_]([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})$")

    def get_available_usb_printers():
        """Get iterable of available USB label printers that are currently plugged in."""

        def get_local_printers():
            """Get iterable of local printers."""
            for printer_info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
                yield printer_info[2]

        def extract_vid_pid(name: str):
            """Return (vid, pid) strings from printer name, or None if not a label printer."""
            match = _VID_PID_RE.search(name)
            if match:
                return match.group(1).upper(), match.group(2).upper()
            return None

        def is_plugged_in(vid: str, pid: str) -> bool:
            """Check if a USB device with given VID:PID is currently connected."""
            entities = wmi.WMI().query(
                "SELECT * FROM Win32_PnPEntity "
                f"WHERE PNPDeviceID LIKE '%VID_{vid}&PID_{pid}%'"
            )
            return len(entities) > 0

        for name in get_local_printers():
            vid_pid = extract_vid_pid(name)
            if vid_pid is not None and is_plugged_in(*vid_pid):
                yield name

    def print_image(img):  # pylint: disable=too-many-locals
        """Print a given image."""

        printer = next(get_available_usb_printers(), None)
        if printer is None:
            raise RuntimeError("No label printer found plugged in")

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
