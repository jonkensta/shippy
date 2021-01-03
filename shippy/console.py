"""Methods for console user interaction."""

import typing
import difflib

import PyInquirer


def query_unit(units: typing.Dict[str, int]) -> typing.Optional[str]:
    """Query a name of a unit from the user."""
    answer = PyInquirer.prompt(
        {"type": "input", "name": "unit", "message": "Enter name of unit:"}
    )
    unit = answer.get("unit")
    if unit is None:
        return None

    def get_matches(unit):
        num_matches, cutoff = 4, 0.0
        return difflib.get_close_matches(unit, units, num_matches, cutoff)

    matches = get_matches(unit)
    choices = [dict(name=match) for match in matches]

    answer = PyInquirer.prompt(
        {
            "type": "list",
            "message": "Select match:",
            "name": "unit",
            "choices": choices,
        }
    )
    unit = answer.get("unit")
    return unit


def query_weight() -> typing.Optional[int]:
    """Query a weight from the user."""

    def validate(weight):
        try:
            weight = int(weight)
        except (TypeError, ValueError):
            return "Weight must be an integer value."

        if weight <= 0:
            return "Weight must be positive."

        return True

    answer = PyInquirer.prompt(
        {
            "type": "input",
            "name": "weight",
            "message": "Please enter weight in pounds:",
            "validate": validate,
        }
    )
    weight = answer.get("weight")
    return int(weight)


def query_request_id() -> typing.Optional[
    typing.Union[typing.Tuple[str, int, int], int]
]:
    """Query a request ID from the user."""

    def validate(request_id):
        try:
            _, inmate_id, index = request_id.split("-")
        except ValueError:
            try:
                int(request_id)
            except ValueError:
                return "Invalid request ID."
            else:
                return True
        else:
            try:
                int(inmate_id), int(index)
            except ValueError:
                return "Invalid request ID."
            else:
                return True

    answer = PyInquirer.prompt(
        {
            "type": "input",
            "name": "request_id",
            "message": "Please scan or enter the request ID:",
            "validate": validate,
        }
    )
    request_id = answer["request_id"]

    try:
        jurisdiction, inmate_id, index = request_id.split("-")
    except ValueError:
        return int(request_id)
    else:
        return jurisdiction, int(inmate_id), int(index)


def query_address() -> typing.Optional[typing.Dict[str, str]]:
    """Query an address from the user."""
    answers = PyInquirer.prompt(
        [
            {"type": "input", "name": "name", "message": "Enter name:"},
            {"type": "input", "name": "street1", "message": "Enter street1:"},
            {"type": "input", "name": "street2", "message": "Enter street2:"},
            {"type": "input", "name": "city", "message": "Enter city:"},
            {"type": "input", "name": "state", "message": "Enter state:"},
            {"type": "input", "name": "zipcode", "message": "Enter zipcode:"},
        ]
    )
    return answers
