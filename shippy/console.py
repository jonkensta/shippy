"""
Functions for user interaction
"""

import typing
import difflib
import functools


class ConsoleInputError(Exception):
    """Invalid user input."""


def console_retry(query):
    """Retry a console command upon bad input."""

    @functools.wraps(query)
    def inner(*args, **kwargs):
        while True:
            try:
                return query(*args, **kwargs)
            except ConsoleInputError as error:
                print(f"bad input: {error}")
                continue

    return inner


@console_retry
def query_yes_no(question: str) -> bool:
    """Get the user to answer a yes-or-no question."""
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    choice = input(question + " [y/n] ").lower()

    try:
        return valid[choice]
    except KeyError:
        raise ConsoleInputError("respond with 'yes' or 'no'.")


@console_retry
def query_unit(units: typing.Dict[str, int]) -> str:
    """Query a name of a unit from the user."""
    unit = input("Enter name of unit: ").upper()
    num_matches, cutoff = 4, 0.0
    matches = difflib.get_close_matches(unit, units, num_matches, cutoff)

    for index, match in enumerate(matches, start=1):
        print(f"[{index}] : {match}")

    choice = input(f"Choose [1 - {num_matches}] corresponding to above: ")

    try:
        return str(matches[int(choice) - 1])
    except (ValueError, IndexError):
        raise ConsoleInputError("invalid index given")


@console_retry
def query_weight() -> int:
    """Query a weight from the user."""
    try:
        pounds = int(input("Enter weight in pounds: "))
    except ValueError:
        raise ConsoleInputError("invalid weight given")
    else:
        total_in_ounces = 16 * pounds
        return total_in_ounces


@console_retry
def query_request_id() -> typing.Union[int, typing.Tuple[str, int, int]]:
    """Query a request ID from the user."""
    request_id = input("Please scan request ID: ")

    try:
        return int(request_id)
    except ValueError:
        try:
            jurisdiction, inmate_id, index = request_id.split("-")
            return jurisdiction, int(inmate_id), int(index)
        except ValueError:
            raise ConsoleInputError("invalid request ID given")
