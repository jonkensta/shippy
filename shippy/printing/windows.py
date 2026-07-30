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
    _SERIAL_RE = re.compile(r"[\s\-_]([0-9A-Za-z]{6,})$")

    # Top-level USB device-instance ID, e.g. ``USB\VID_2E3C&PID_5760\Q529...``.
    # The trailing segment is the per-unit serial (or, lacking one, a port-based
    # instance path). An optional ``&REV_xxxx`` in the second segment is allowed,
    # but interface/child nodes (``...&MI_00\...``) do not match, so this keys each
    # match to one physical device rather than several PnP nodes.
    _USB_INSTANCE_RE = re.compile(
        r"^USB\\VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})"
        r"(?:&REV_[0-9A-Fa-f]{4})?\\([^\\]+)$",
        re.IGNORECASE,
    )

    # USB VID/PID prefix of a device-instance ID. Used to scope a serial match to
    # a real USB device and read its VID/PID. Tolerant of composite/``&REV_``
    # forms; the exact serial-tail comparison does the actual disambiguation.
    _USB_VID_PID_PREFIX_RE = re.compile(
        r"^USB\\VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", re.IGNORECASE
    )

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

    def _usb_query(name):
        """Return ``(like_pattern, serial)`` for a printer name, or None.

        ``serial`` is the exact serial to require on a device-instance tail
        (serial-named queue), or ``None`` for a legacy VID:PID queue. Prefers a
        VID:PID suffix (legacy, generic) over a serial suffix. The trailing name
        token is only a candidate; the WMI query plus the serial-tail equality in
        :func:`_connected_device_keys` are what actually confirm a matching device.
        """
        vid_pid = _VID_PID_RE.search(name)
        if vid_pid:
            vid, pid = vid_pid.group(1).upper(), vid_pid.group(2).upper()
            return f"%VID[_]{vid}&PID[_]{pid}%", None

        serial = _SERIAL_RE.search(name)
        if serial:
            return f"%PID[_]%{serial.group(1)}", serial.group(1)

        return None

    def _connected_device_keys(connection, like_pattern, serial):
        """Physical ``(vid, pid, serial)`` keys of connected devices matching.

        ``ConfigManagerErrorCode = 0`` restricts the result to devices that are
        present and working, excluding stale/"not connected" ghost nodes.

        For a serial-named queue (``serial`` given), the LIKE is only a cheap
        pre-filter: a device is accepted only if its instance tail equals the
        serial exactly, so a suffix-colliding or unrelated unit cannot bind. For
        a legacy VID:PID queue, only device-instance nodes are counted
        (interface/child nodes dropped) so one physical printer counts once.
        """
        rows = connection.query(
            "SELECT PNPDeviceID FROM Win32_PnPEntity "
            f"WHERE PNPDeviceID LIKE '{like_pattern}' "
            "AND ConfigManagerErrorCode = 0"
        )
        keys = set()
        for row in rows:
            device_id = row.PNPDeviceID or ""
            if serial is not None:
                prefix = _USB_VID_PID_PREFIX_RE.match(device_id)
                tail = device_id.rsplit("\\", 1)[-1]
                if prefix and tail.upper() == serial.upper():
                    keys.add(
                        (
                            prefix.group(1).upper(),
                            prefix.group(2).upper(),
                            tail.upper(),
                        )
                    )
            else:
                match = _USB_INSTANCE_RE.match(device_id)
                if match:
                    vid, pid, tail = match.groups()
                    keys.add((vid.upper(), pid.upper(), tail.upper()))
        return keys

    def _get_local_printer_names():
        """Get iterable of local printer names."""
        for printer_info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
            yield printer_info[2]

    def get_connected_label_printers():
        """Return connected label printers as ``(name, is_serial, device_keys)``.

        Each installed local printer whose Windows name ends with a USB
        identifier (see :func:`print_image`) is matched against the currently
        connected USB devices via WMI. A printer is included only if a matching,
        working USB device is actually present.

        ``device_keys`` is the set of ``(vid, pid, serial)`` identities of the
        physical devices behind the queue, and ``is_serial`` records whether the
        match came from a unique serial number (specific to one unit) or a
        VID:PID pair (generic — shared by every unit of a model).
        """

        connection = wmi.WMI()

        printers = []
        for name in _get_local_printer_names():
            query = _usb_query(name)
            if query is None:
                continue
            like_pattern, serial = query
            device_keys = _connected_device_keys(connection, like_pattern, serial)
            if device_keys:
                printers.append((name, serial is not None, device_keys))

        return printers

    def _decode_bits(value, table):
        """Decode a bitfield into a human-readable list of set flag names."""
        names = [name for bit, name in table.items() if value & bit]
        return ", ".join(names) if names else "none"

    def _snapshot_one_queue(connection, index, info):
        """Return report lines for a single print queue and its gate results."""
        name = info.get("pPrinterName", "")
        status = info.get("Status", 0)
        attributes = info.get("Attributes", 0)

        lines = [
            f"  [{index}] name={name!r}",
            f"        port={info.get('pPortName', '')!r}",
            f"        status=0x{status:08x} "
            f"({_decode_bits(status, _PRINTER_STATUS_BITS)})",
            f"        attributes=0x{attributes:08x} "
            f"({_decode_bits(attributes, _PRINTER_ATTRIBUTE_BITS)})",
        ]

        query = _usb_query(name)
        if query is None:
            lines.append(
                "        gate 1 (name USB identifier): NO MATCH (name must end "
                "in a serial, e.g. ' Q529E65K5250028', or ' 0922:0028')"
            )
            lines.append("        => eligible: NO")
            return lines

        like_pattern, serial = query
        kind = f"serial {serial}" if serial is not None else "VID:PID"
        lines.append(f"        gate 1 (name USB identifier): {kind}")
        try:
            keys = _connected_device_keys(connection, like_pattern, serial)
            lines.append(
                f"        gate 2 (USB present LIKE {like_pattern!r}): "
                f"{'YES' if keys else 'NO'}"
            )
            for key in sorted(keys):
                lines.append(f"          device {_describe_device(key)}")
            lines.append(f"        => eligible: {'YES' if keys else 'NO'}")
        except Exception as exc:  # pylint: disable=broad-except
            lines.append(f"        gate 2 (USB present): ERROR {exc!r}")
            lines.append("        => eligible: UNKNOWN (WMI error)")

        return lines

    def _snapshot_print_queues():
        """Return report lines describing every local print queue and its gate results."""
        lines = [
            "-- Local print queues (EnumPrinters LOCAL, level 2) --",
            "   ('eligible' = passes both gates; several queues can be eligible "
            "at once — the Verdict says which one shippy would print to)",
        ]
        try:
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL, None, 2)
        except Exception as exc:  # pylint: disable=broad-except
            lines.append(f"  ERROR enumerating printers: {exc!r}")
            return lines

        if not printers:
            lines.append("  (no local print queues found)")
            return lines

        # One connection for this whole section, mirroring the selector. Opening
        # one per queue made the report's own COM traffic scale with the printer
        # count, which can itself tip a struggling WMI service over. (A full
        # snapshot still opens three in total — this section, the USB-device
        # section, and the verdict's resolver — but that is a fixed cost rather
        # than one growing with the number of installed queues.)
        #
        # Note the connection can also die mid-loop, in which case every
        # remaining queue reports "UNKNOWN (WMI error)" rather than just the
        # first. That is deliberate: the report keeps going and shows the
        # failure is systemic, where the selector aborts on the first error.
        try:
            connection = wmi.WMI()
        except Exception as exc:  # pylint: disable=broad-except
            lines.append(f"  ERROR opening WMI connection: {exc!r}")
            return lines

        for index, info in enumerate(printers, start=1):
            lines += _snapshot_one_queue(connection, index, info)

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

        Reports the two per-queue detection gates (name USB-identifier match,
        and live USB presence) separately, then a verdict. Note that a failure
        need not have a failing gate: when several distinct printers are
        connected every gate passes and selection is refused anyway, and a
        queue that passes both gates can still fail to open.
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
            # One query, via the same resolver print_image uses: the report
            # cannot describe one enumeration while judging another.
            outcome, detail, printers = _resolve_selection()

            lines.append(f"eligible queues: {len(printers)}")
            for name, is_serial, _ in printers:
                kind = "serial-named" if is_serial else "legacy VID:PID"
                lines.append(f"  -> {name}  ({kind})")
            if printers:
                devices = set().union(*(keys for _, _, keys in printers))
                lines.append(f"distinct physical printers connected: {len(devices)}")
                for key in sorted(devices):
                    lines.append(f"  -> {_describe_device(key)}")

            if outcome == "none":
                lines.append(
                    "  => selection FAILS: 'No label printer found plugged in'"
                )
            elif outcome == "ambiguous":
                lines.append(
                    "  => selection FAILS: more than one label printer is "
                    "connected and shippy will not guess between them"
                )
            else:
                lines.append(f"  => shippy would print to {detail!r}")
                # Selection only proves a matching USB device is present; it
                # never opens the queue. A paused/offline queue or a broken
                # driver still fails after this point, so do not promise
                # success — point at the status bits reported above.
                lines.append(
                    "     (queue not opened by this check — if printing still "
                    "fails, check that queue's status bits above)"
                )
        except Exception as exc:  # pylint: disable=broad-except
            lines.append(f"detection raised: {exc!r}")
            lines.append("  => selection FAILS: the printer query itself errored")

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

    def _diagnostics_hint():
        """Best-effort ``" Diagnostics written to ..."`` suffix for an error message."""
        try:
            return f" Diagnostics written to {log_printer_diagnostics()}."
        except Exception:  # pylint: disable=broad-except
            return ""  # Never let diagnostics logging mask the original failure.

    def _describe_device(key):
        """Human-readable identity of a ``(vid, pid, tail)`` device key.

        The tail is the unit's USB serial when it has one, but for a serial-less
        device Windows substitutes a port-based instance path — calling that a
        "serial" would send the user looking for a sticker that does not exist.
        """
        vid, pid, tail = key
        looks_like_serial = tail.isalnum()
        return f"{vid}:{pid} {'serial' if looks_like_serial else 'instance'} {tail}"

    def _resolve_selection():
        """Resolve what printing would do, without raising or formatting.

        Returns ``(outcome, detail, printers)``, where ``printers`` is the
        :func:`get_connected_label_printers` result the decision was made from
        and ``outcome``/``detail`` are one of:

          * ``("ok", queue_name)`` — this queue would be printed to.
          * ``("none", None)`` — no queue passes both gates.
          * ``("ambiguous", (devices, queues))`` — several distinct physical
            printers are connected, so the choice is refused.

        Both :func:`_select_printer` (which raises) and the diagnostics verdict
        (which reports) go through this, so a prediction cannot drift out of
        sync with what printing actually does. ``printers`` is returned rather
        than re-queried by the caller so that a single report cannot describe
        one enumeration while judging another. Propagates query errors.
        """
        printers = get_connected_label_printers()
        if not printers:
            return "none", None, printers

        devices = set().union(*(keys for _, _, keys in printers))
        if len(devices) > 1:
            # The ambiguity is between physical devices, and those need not be
            # one per queue: a single legacy VID:PID queue can match several
            # same-model units.
            return "ambiguous", (devices, [name for name, _, _ in printers]), printers

        serial_named = [name for name, is_serial, _ in printers if is_serial]
        chosen = serial_named[0] if serial_named else printers[0][0]
        return "ok", chosen, printers

    def _select_printer():
        """Return the Windows queue name to print to, or raise a clear error.

        Every raise here carries a diagnostics-log path, so a WMI outage is as
        diagnosable as the "no printer found" case it would be mistaken for.
        """
        try:
            outcome, detail, _ = _resolve_selection()
        except Exception as exc:  # pylint: disable=broad-except
            # A WMI/enumeration failure is exactly what the diagnostics log
            # exists for; route it through the same path rather than surfacing
            # a raw COM error with no captured state.
            raise RuntimeError(
                f"Could not query connected printers ({exc})." + _diagnostics_hint()
            ) from exc

        if outcome == "none":
            raise RuntimeError(
                "No label printer found plugged in." + _diagnostics_hint()
            )

        if outcome == "ambiguous":
            devices, queues = detail
            raise RuntimeError(
                f"More than one label printer is currently connected "
                f"({len(devices)} devices: "
                f"{', '.join(_describe_device(d) for d in sorted(devices))}); "
                f"shippy cannot choose between them — connect only one printer "
                f"at a time. Matching queues: {', '.join(queues)}."
                + _diagnostics_hint()
            )

        return detail

    def print_image(img):  # pylint: disable=too-many-locals
        """Print a given image.

        A label printer is recognized by a trailing USB identifier in its Windows
        printer name, separated by a space, hyphen, or underscore:

          * a USB serial number, e.g. ``Front-Desk PM-2411-BT Q529E65K5250028``
            (preferred: unique per physical unit, so two printers of the same
            model can be named distinctly and only the connected one matches), or
          * a ``VID:PID`` pair, e.g. ``PM-2411-BT 2E3C:5760`` (legacy: shared by
            all units of a model, so it cannot tell two same-model units apart).

        Selection is by *physical device*: queues resolving to the same connected
        printer collapse to one (a serial-named queue is preferred over a generic
        VID:PID one), so a stale/duplicate queue does not block printing. Only
        when two or more distinct printers are connected at once is the choice
        genuinely ambiguous, and this raises rather than guess.
        """

        printer = _select_printer()

        @contextlib.contextmanager
        def create_printer_context(printer_name):
            # Acquire before the try: if CreateDC itself fails there is no
            # device context to release, and running the finally anyway raised
            # UnboundLocalError, replacing the real error with a confusing one.
            context = win32ui.CreateDC()
            try:
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
