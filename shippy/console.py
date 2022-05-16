"""Methods for console user interaction."""

import typing
import difflib

import questionary


def query_unit(units: typing.Dict[str, int]) -> typing.Optional[str]:
    """Query a name of a unit from the user."""
    unit = questionary.text("Enter name of unit:").ask().upper()
    if unit is None:
        return None

    unit = unit.upper()

    def get_matches(unit):
        num_matches, cutoff = 4, 0.0
        return difflib.get_close_matches(unit, list(units), num_matches, cutoff)

    matches = get_matches(unit)
    return questionary.select("Select match:", choices=matches).ask()


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
    return weight and int(weight)


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
                return "Request ID must be an integer."
            else:
                return True
        else:
            try:
                int(inmate_id), int(index)
            except ValueError:
                return "Inmate ID and index must be an integer."
            else:
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
    else:
        return jurisdiction, int(inmate_id), int(index)


def query_address() -> typing.Optional[typing.Dict[str, str]]:
    """Query an address from the user."""
    prompts = {
        "name": "Enter name:",
        "street1": "Enter street1:",
        "street2": "Enter street2:",
        "city": "Enter city:",
        "state": "Enter state:",
        "zipcode": "Enter zipcode:",
    }

    questions = {name: questionary.text(prompt) for name, prompt in prompts.items()}

    address = {}
    for name, question in questions.items():
        response = question.ask()
        if response is None:
            return None
        address[name] = response

    return address
