"""Methods for console user interaction."""

import contextlib
import typing

import googlemaps  # type: ignore
import questionary
from prompt_toolkit.completion import ThreadedCompleter

from .addresses import AddressParser
from .autocompletion import GoogleMapsCompleter
from .server import JURISDICTIONS


def query_unit(units: typing.Mapping[str, typing.Any]) -> typing.Optional[str]:
    """Query a name of a unit from the user."""

    def validate(unit):
        return unit.upper() in units

    style = questionary.Style(
        [
            ("completion-menu", "bg:#2c3e50"),
            ("completion-menu.completion", "bg:#2c3e50 #ecf0f1"),
            ("completion-menu.completion.current", "bg:#16a085 #ecf0f1"),
        ]
    )

    unit = questionary.autocomplete(
        "Enter name of unit:",
        choices=list(units),
        validate=validate,
        style=style,
    ).ask()

    return unit.upper() if unit is not None else None


def query_weight() -> typing.Optional[int]:
    """Query a weight from the user."""

    def validate(weight):
        try:
            weight = int(weight)
        except (TypeError, ValueError):
            return "Weight must be an integer."

        if weight <= 0:
            return "Weight must be strictly positive."

        return True

    weight = questionary.text("Please enter weight in pounds:", validate=validate).ask()
    return int(weight) if weight is not None else None


SMALL_BOX_QUESTION = (
    "Is the box 1,728 cubic inches or less (length x width x height, each side "
    "rounded up) with no side over 22 inches?"
)

SMALL_BOX_EXAMPLES = (
    "  Box size: round each side UP to a whole inch, then multiply.",
    "    Qualifies: 12x12x12, 18x12x8, 16x12x9, 20x10x8",
    "    Doesn't:   14x12x11 (1,848 cubic inches), 24x10x7 (side over 22 inches)",
    "  If you're not sure, answer No.",
)


def query_small_box(weight: int, min_weight: int) -> typing.Optional[bool]:
    """Ask whether a package of ``weight`` pounds is in a box of one cubic foot or less.

    The box qualifies when, with each side rounded up to the next whole inch
    (as USPS measures), length x width x height is at most 1,728 cubic inches
    and no side is over 22 inches. That is the loosest bound where declaring
    the configured small box gives the same price as the real box: both are
    priced by actual weight, and neither passes the 22-inch surcharge length.

    Returns False without asking below ``min_weight`` pounds, where the box size
    can't change the rate. Returns None if the volunteer cancels (Ctrl+C).
    The default answer is No: a wrong "yes" earns a USPS adjustment charge.
    """
    if weight < min_weight:
        return False
    for line in SMALL_BOX_EXAMPLES:
        questionary.print(line, style="fg:white")
    return questionary.confirm(SMALL_BOX_QUESTION, default=False).ask()


def query_request_id() -> (
    typing.Optional[typing.Union[typing.Tuple[str, int, int], int]]
):
    """Query a request ID from the user."""

    def validate(request_id):
        try:
            jurisdiction, inmate_id, index = request_id.split("-")
        except ValueError:
            try:
                int(request_id)
            except ValueError:
                return "Request ID must be an integer."

            return True

        if jurisdiction.strip().upper() not in JURISDICTIONS:
            return "Jurisdiction must be one of: " + ", ".join(sorted(JURISDICTIONS))

        try:
            int(inmate_id), int(index)
        except ValueError:
            return "Inmate ID and index must be an integer."

        return True

    request_id = questionary.text(
        "Please enter the request ID:", validate=validate
    ).ask()

    if request_id is None:
        return None

    try:
        jurisdiction, inmate_id, index = request_id.split("-")
    except ValueError:
        return int(request_id)

    return jurisdiction, int(inmate_id), int(index)


def confirm_tossed() -> bool:
    """Ask the user to confirm shipping a request that was marked tossed."""
    answer = questionary.confirm(
        "Buy postage for this TOSSED request anyway?", default=False
    ).ask()
    return bool(answer)


def query_address(gmaps: googlemaps.Client) -> typing.Optional[typing.Dict[str, str]]:
    """Query an address from the user."""
    name = questionary.text("Enter name:").ask()
    if name is None:
        return None

    company = questionary.text("Enter company:").ask()
    if company is None:
        return None

    gmaps_completer = GoogleMapsCompleter(gmaps)
    threaded_completer = ThreadedCompleter(gmaps_completer)

    def validate(text):
        return True if len(text) > 0 else "Please enter an address."

    address_text = questionary.autocomplete(
        "Enter address:",
        choices=[],
        completer=threaded_completer,
        validate=validate,
    ).ask()

    if address_text is None:
        return None

    parse_address = AddressParser(gmaps)
    address = parse_address(address_text)

    address["name"] = name
    address["company"] = company

    return address


@contextlib.contextmanager
def task_message(msg):
    """Capture a task context with messaging."""
    try:
        questionary.print(f"{msg} ... ", end="", flush=True)
        yield
    except Exception:
        questionary.print("error!", style="fg:red", flush=True)
        raise

    questionary.print("done!", style="fg:orange", flush=True)


WELCOME = r"""
    ________  ____     _____ __    _             _
   /  _/ __ )/ __ \   / ___// /_  (_)___  ____  (_)___  ____ _
   / // __  / /_/ /   \__ \/ __ \/ / __ \/ __ \/ / __ \/ __ `/
 _/ // /_/ / ____/   ___/ / / / / / /_/ / /_/ / / / / / /_/ /
/___/_____/_/       /____/_/ /_/_/ .___/ .___/_/_/ /_/\__, /
                                /_/   /_/            /____/
"""
