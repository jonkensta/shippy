"""Methods for console user interaction."""

import contextlib
import typing

import googlemaps  # type: ignore
import questionary
from prompt_toolkit.completion import ThreadedCompleter

from .addresses import AddressParser
from .autocompletion import GoogleMapsCompleter


def query_unit(units: typing.Dict[str, int]) -> typing.Optional[str]:
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


def query_request_id() -> (
    typing.Optional[typing.Union[typing.Tuple[str, int, int], int]]
):
    """Query a request ID from the user."""

    def validate(request_id):
        try:
            _, inmate_id, index = request_id.split("-")
        except ValueError:
            try:
                int(request_id)
            except ValueError:
                return "Request ID must be an integer."

            return True

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
