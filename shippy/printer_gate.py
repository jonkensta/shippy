"""Wait for a usable label printer before postage is bought.

Crews often start shipping before Windows has finished recognising a freshly
plugged-in label printer, so postage gets bought for a label that cannot print.
The gate re-checks for a usable printer every few seconds and lets the volunteer
carry on once one appears, or press Enter to continue without one; labels that
cannot print are then saved to the to-print folder for the label watcher.
"""

import sys
import time
from typing import Callable

import questionary
from ibp_printing import discover
from ibp_printing.log import get_logger

logger = get_logger("shippy.printer_gate")

# How often to look for a printer while waiting.
POLL_INTERVAL_S = 2.0

WAITING_STYLE = "bold fg:ansiblack bg:ansiyellow"


def usable_printer_names() -> list[str]:
    """Names of the label printers that can be printed to right now.

    discover() only lists printers and devices; it never sends a job. A
    discovery failure counts as "no printer" so it can never block shipping
    for good (the volunteer can still continue anyway).
    """
    try:
        return [candidate.name for candidate in discover().usable]
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("printer discovery failed while waiting for a printer")
        return []


def _wait_for_enter_windows(timeout_s: float) -> bool:
    """Windows: wait up to timeout_s for Enter in the console."""
    import msvcrt  # pylint: disable=import-outside-toplevel,import-error

    deadline = time.monotonic() + timeout_s
    while True:
        while msvcrt.kbhit():  # type: ignore[attr-defined]
            key = msvcrt.getwch()  # type: ignore[attr-defined]
            if key == "\x03":
                raise KeyboardInterrupt
            if key in ("\r", "\n"):
                return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))


def _wait_for_enter_posix(timeout_s: float) -> bool:
    """POSIX: wait up to timeout_s for a line (Enter) on stdin."""
    import select  # pylint: disable=import-outside-toplevel

    readable, _, _ = select.select([sys.stdin], [], [], timeout_s)
    if not readable:
        return False
    sys.stdin.readline()
    return True


def wait_for_enter(timeout_s: float) -> bool:
    """Wait up to timeout_s for the volunteer to press Enter; True if they did.

    Ctrl+C raises KeyboardInterrupt as usual.
    """
    if sys.platform == "win32":
        return _wait_for_enter_windows(timeout_s)
    return _wait_for_enter_posix(timeout_s)


def wait_for_printer(
    *,
    find_printers: Callable[[], list[str]] = usable_printer_names,
    wait_for_continue: Callable[[float], bool] = wait_for_enter,
    say: Callable[..., None] = questionary.print,
    interval_s: float = POLL_INTERVAL_S,
) -> bool:
    """Block until a usable label printer exists or the volunteer continues anyway.

    Returns immediately and silently when a printer is already usable.

    Returns:
        True once a printer is usable; False if the volunteer chose to continue
        without one.

    Raises:
        KeyboardInterrupt: the volunteer pressed Ctrl+C.
    """
    names = find_printers()
    if names:
        return True

    logger.warning("no usable label printer; waiting for one")
    say("")
    say("  NO LABEL PRINTER FOUND  ", style=WAITING_STYLE)
    say(
        "  Plug in the label printer and turn it on. This continues by itself "
        "as soon as the printer is ready (it can take a minute after plugging "
        "it in).\n"
        "  To continue without a printer, press Enter: labels that cannot print "
        "are saved to the Downloads\\to-print folder, and the label watcher "
        "prints them once a printer works.\n"
        "  Press Ctrl+C to quit.",
        style="fg:yellow",
    )

    started = time.monotonic()
    while True:
        if wait_for_continue(interval_s):
            logger.warning(
                "volunteer continued without a label printer after %.0f s",
                time.monotonic() - started,
            )
            say("  Continuing without a label printer.", style="fg:yellow")
            return False
        names = find_printers()
        if names:
            logger.info(
                "label printer ready after %.0f s: %s",
                time.monotonic() - started,
                ", ".join(names),
            )
            say(f"  Label printer ready: {names[0]}", style="fg:green")
            return True
