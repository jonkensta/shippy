"""Printing on win32 platform."""

import contextlib
import os
import re
import subprocess
import tempfile

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

    # Printer status bits worth surfacing in diagnostics (win32print.PRINTER_STATUS_*).
    _PRINTER_STATUS_BITS = {
        0x00000001: "PAUSED",
        0x00000002: "ERROR",
        0x00000008: "PAPER_JAM",
        0x00000010: "PAPER_OUT",
        0x00000020: "MANUAL_FEED",
        0x00000040: "PAPER_PROBLEM",
        0x00000080: "OFFLINE",
        0x00000100: "IO_ACTIVE",
        0x00000200: "BUSY",
        0x00000400: "PRINTING",
        0x00001000: "NOT_AVAILABLE",
        0x00002000: "WAITING",
        0x00400000: "DOOR_OPEN",
        0x00800000: "SERVER_UNKNOWN",
        0x01000000: "POWER_SAVE",
    }

    # Printer attribute bits worth surfacing in diagnostics.
    _PRINTER_ATTRIBUTE_BITS = {
        0x00000400: "WORK_OFFLINE",
        0x00000040: "LOCAL",
        0x00000080: "NETWORK",
        0x00000200: "SHARED",
    }

    def _extract_vid_pid(name):
        """Return (vid, pid) strings from printer name, or None if not a label printer."""
        match = _VID_PID_RE.search(name)
        if match:
            return match.group(1).upper(), match.group(2).upper()
        return None

    def _is_plugged_in(vid, pid):
        """Check if a USB device with given VID:PID is currently connected."""
        entities = wmi.WMI().query(
            "SELECT * FROM Win32_PnPEntity "
            f"WHERE PNPDeviceID LIKE '%VID_{vid}&PID_{pid}%'"
        )
        return len(entities) > 0

    def _get_local_printer_names():
        """Get iterable of local printer names."""
        for printer_info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
            yield printer_info[2]

    def get_available_usb_printers():
        """Get iterable of available USB label printers that are currently plugged in."""
        for name in _get_local_printer_names():
            vid_pid = _extract_vid_pid(name)
            if vid_pid is not None and _is_plugged_in(*vid_pid):
                yield name

    def _decode_bits(value, table):
        """Decode a bitfield into a human-readable list of set flag names."""
        names = [name for bit, name in table.items() if value & bit]
        return ", ".join(names) if names else "none"

    def _snapshot_print_queues():
        """Return report lines describing every local print queue and its gate results."""
        lines = ["-- Local print queues (EnumPrinters LOCAL, level 2) --"]
        try:
            printers = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL, None, 2
            )
        except Exception as exc:  # pylint: disable=broad-except
            lines.append(f"  ERROR enumerating printers: {exc!r}")
            return lines

        if not printers:
            lines.append("  (no local print queues found)")
            return lines

        for index, info in enumerate(printers, start=1):
            name = info.get("pPrinterName", "")
            port = info.get("pPortName", "")
            status = info.get("Status", 0)
            attributes = info.get("Attributes", 0)

            lines.append(f"  [{index}] name={name!r}")
            lines.append(f"        port={port!r}")
            lines.append(
                f"        status=0x{status:08x} ({_decode_bits(status, _PRINTER_STATUS_BITS)})"
            )
            lines.append(
                f"        attributes=0x{attributes:08x} "
                f"({_decode_bits(attributes, _PRINTER_ATTRIBUTE_BITS)})"
            )

            vid_pid = _extract_vid_pid(name)
            if vid_pid is None:
                lines.append(
                    "        gate 1 (name VID:PID): NO MATCH "
                    "(name must end in e.g. ' 0922:0028')"
                )
                lines.append("        => would be used: NO")
                continue

            vid, pid = vid_pid
            lines.append(f"        gate 1 (name VID:PID): {vid}:{pid}")
            try:
                present = _is_plugged_in(vid, pid)
                lines.append(
                    f"        gate 2 (USB present VID_{vid}&PID_{pid}): "
                    f"{'YES' if present else 'NO'}"
                )
                lines.append(
                    f"        => would be used: {'YES' if present else 'NO'}"
                )
            except Exception as exc:  # pylint: disable=broad-except
                lines.append(f"        gate 2 (USB present): ERROR {exc!r}")
                lines.append("        => would be used: UNKNOWN (WMI error)")

        return lines

    def _snapshot_usb_devices():
        """Return report lines listing all USB PnP entities (the DYMO's ground truth)."""
        lines = ["-- USB devices (Win32_PnPEntity LIKE 'USB%') --"]
        try:
            entities = wmi.WMI().query(
                "SELECT PNPDeviceID, Name, Status, ConfigManagerErrorCode "
                "FROM Win32_PnPEntity WHERE PNPDeviceID LIKE 'USB%'"
            )
        except Exception as exc:  # pylint: disable=broad-except
            lines.append(f"  ERROR querying WMI: {exc!r}")
            return lines

        if not entities:
            lines.append("  (no USB devices returned by WMI)")
            return lines

        for entity in entities:
            pnp_id = getattr(entity, "PNPDeviceID", "") or ""
            name = getattr(entity, "Name", "") or ""
            status = getattr(entity, "Status", "") or ""
            cm_error = getattr(entity, "ConfigManagerErrorCode", "")
            lines.append(f"  name={name!r}")
            lines.append(f"      PNPDeviceID={pnp_id}")
            lines.append(f"      status={status!r} ConfigManagerErrorCode={cm_error}")
        return lines

    def snapshot_printer_state():
        """Build a full, human-readable snapshot of printer/USB state for diagnosis.

        Separates the two detection gates (name VID:PID match, and live USB
        presence) so a single capture reveals which one is failing.
        """
        lines = [
            "==================================================================",
            "shippy printer diagnostics",
            "platform=win32 pywin32=available",
            "==================================================================",
            "",
        ]
        lines += _snapshot_print_queues()
        lines.append("")
        lines += _snapshot_usb_devices()
        lines.append("")

        lines.append("-- Verdict --")
        try:
            usable = list(get_available_usb_printers())
            if usable:
                lines.append(f"usable label printers found: {len(usable)}")
                for name in usable:
                    lines.append(f"  -> {name}")
            else:
                lines.append("usable label printers found: 0")
                lines.append("  (this is the condition that raises the RuntimeError)")
        except Exception as exc:  # pylint: disable=broad-except
            lines.append(f"detection raised: {exc!r}")

        return "\n".join(lines)

    def _diagnostics_log_path():
        """Return the path to the rotating diagnostics log file."""
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        directory = os.path.join(base, "shippy")
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, "printer-diagnostics.log")

    def log_printer_diagnostics():
        """Append a diagnostic snapshot to the log file; return the file path.

        Rotates a single backup once the log exceeds ~1 MB so it never grows
        unbounded on a long-running shipping machine.
        """
        path = _diagnostics_log_path()

        try:
            if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
                backup = path + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.replace(path, backup)
        except OSError:
            pass  # Rotation is best-effort; never block on it.

        report = snapshot_printer_state()
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(report)
            handle.write("\n\n")

        return path

    def print_image(img):  # pylint: disable=too-many-locals
        """Print a given image."""

        printer = next(get_available_usb_printers(), None)
        if printer is None:
            hint = ""
            try:
                hint = f" Diagnostics written to {log_printer_diagnostics()}."
            except Exception:  # pylint: disable=broad-except
                pass  # Never let diagnostics logging mask the original failure.
            raise RuntimeError("No label printer found plugged in." + hint)

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

    def snapshot_printer_state():
        """Diagnostics are only meaningful with pywin32 installed."""
        return (
            "shippy printer diagnostics unavailable: pywin32 is not installed, "
            "so the win32 printer detection path is not in use on this machine."
        )
