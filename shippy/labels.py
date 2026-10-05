"""Shared label journal glue: duplicate checks and label status tracking.

The journal lives in ibp-printing and is shared with shippy-gui and the label
watcher, so a label bought in either app is seen by both. Its functions never
raise for journal problems; the wrappers here also make sure an unexpected
error can never break shipping (it is logged and ignored).
"""

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import ibp_printing
from ibp_printing.log import get_logger

logger = get_logger("shippy")

APP_NAME = "shippy"

# How far back a label for the same recipient counts as a possible duplicate.
DUPLICATE_WINDOW_HOURS = 12

STATUS_PRINTED = "printed"
STATUS_QUEUED = "queued"
STATUS_CHECK_PRINTER = "check_printer"
STATUS_REFUNDED = "refunded"


@dataclass(frozen=True)
class LabelIdentity:
    """Who a label is for, as the journal knows it."""

    recipient_key: str
    recipient_label: str


def identity_for(address: Mapping[str, Any]) -> LabelIdentity:
    """Build the journal identity of an address dict (name, street1, ...).

    shippy-gui builds the same key from the same fields (street1 and street2
    joined by a space), so both apps see each other's labels.
    """
    name = str(address.get("name") or "")
    street1 = str(address.get("street1") or "")
    street = " ".join(
        part for part in (street1, str(address.get("street2") or "")) if part
    )
    city = str(address.get("city") or "")
    state = str(address.get("state") or "")
    zip_code = str(address.get("zipcode") or address.get("zip") or "")
    key = ibp_printing.recipient_key(name, street, city, state, zip_code)
    label = ", ".join(part for part in (name, street1, city, state) if part)
    return LabelIdentity(recipient_key=key, recipient_label=label)


def tracking_ref(shipment) -> str:
    """The journal's key for a shipment: tracking code, else shipment id."""
    return shipment.tracking_code or shipment.id


def find_duplicates(identity: LabelIdentity) -> list:
    """Recent labels for the same recipient; empty if the journal is unavailable."""
    try:
        return list(
            ibp_printing.find_duplicates(
                identity.recipient_key, within_hours=DUPLICATE_WINDOW_HOURS
            )
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("duplicate-label check failed; not checking")
        return []


def pending_labels() -> list:
    """Labels still waiting to print; empty if the journal is unavailable."""
    try:
        return list(ibp_printing.pending_labels())
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("could not list the labels waiting to print")
        return []


def record_purchase(identity: LabelIdentity, shipment) -> Any:
    """Journal a just-bought label; returns its record (None if not journaled)."""
    try:
        return ibp_printing.record_purchase(
            recipient_key=identity.recipient_key,
            recipient_label=identity.recipient_label,
            tracking_code=tracking_ref(shipment),
            shipment_id=shipment.id,
            app=APP_NAME,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("could not journal the purchase of %s", shipment.id)
        return None


def update_status(shipment, status: str, *, file: Optional[Path] = None) -> None:
    """Journal a label's print outcome; never raises."""
    try:
        ibp_printing.update_status(
            tracking_ref(shipment), status, file=str(file) if file else None
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("could not journal status %s for %s", status, shipment.id)


def retry_meta(
    identity: Optional[LabelIdentity], shipment, record: Any = None
) -> dict[str, Any]:
    """Metadata saved next to a queued label for the label watcher."""
    created = getattr(record, "created", None)
    meta: dict[str, Any] = {
        "tracking_code": tracking_ref(shipment),
        "shipment_id": shipment.id,
        "app": APP_NAME,
        # When postage was bought (epoch seconds, like the journal).
        "created": created if isinstance(created, (int, float)) else time.time(),
    }
    if identity is not None:
        meta["recipient_label"] = identity.recipient_label
        meta["recipient_key"] = identity.recipient_key
    return meta


def format_time(value: Any) -> str:
    """HH:MM of a journal timestamp (epoch seconds) today, else date and time."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value or "?")
    moment = datetime.fromtimestamp(value)
    if moment.date() == datetime.now().date():
        return moment.strftime("%H:%M")
    return moment.strftime("%b %d %H:%M")


def describe_state(record: Any) -> str:
    """What happened to an earlier label, phrased after "is already"."""
    status = getattr(record, "status", "")
    if status == STATUS_QUEUED:
        return "queued — it will print automatically when the printer works"
    if status == STATUS_CHECK_PRINTER:
        return "waiting at the printer: check the printer before reprinting"
    if status == STATUS_PRINTED:
        return f"printed at {format_time(record.updated or record.created)}"
    if status == STATUS_REFUNDED:
        return f"refunded at {format_time(record.updated or record.created)}"
    return (
        f"bought at {format_time(record.created)} (its print outcome is unknown: "
        "check the printer before reprinting)"
    )


def duplicate_question(records: Sequence[Any]) -> str:
    """Ask whether to create a label although one already exists."""
    newest = records[0]  # ibp-printing lists the newest first
    text = (
        f"A label for {newest.recipient_label} is already "
        f"{describe_state(newest)} (tracking {newest.tracking_code})."
    )
    others = len(records) - 1
    if others:
        text += (
            f" {others} other label(s) were made for this address in the last "
            f"{DUPLICATE_WINDOW_HOURS} hours."
        )
    return f"{text} Create another label anyway?"
