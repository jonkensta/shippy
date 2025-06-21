"""Methods for console user interaction."""

import contextlib
import functools
import traceback
import typing

import questionary


def query_unit(units: typing.Dict[str, int]) -> typing.Optional[str]:
    """Query a name of a unit from the user."""

    def validate(unit):
        return unit.upper() in units

    unit = questionary.autocomplete(
        "Enter name of unit:", choices=units, validate=validate
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


def query_address() -> typing.Optional[typing.Dict[str, str]]:
    """Query an address from the user."""
    prompts = {
        "name": "Enter name:",
        "company": "Enter company name:",
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


@contextlib.contextmanager
def task_message(msg):
    """Capture a task context with messaging."""
    try:
        questionary.print(f"{msg} ... ", end="", flush=True)
        yield
    except Exception:
        questionary.print("error!", style="fg:red", flush=True)
        raise

    questionary.print("done!", style="fg:white", flush=True)


def catch_and_print_error(func):
    """Given user an opportunity to see an error before main closes."""

    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            traceback.print_exc()
            questionary.print(f"Error: {exc}", style="fg:red", flush=True)
            input("Hit any key to close")
            raise

    return inner


WELCOME = r"""
    ________  ____     _____ __    _             _
   /  _/ __ )/ __ \   / ___// /_  (_)___  ____  (_)___  ____ _
   / // __  / /_/ /   \__ \/ __ \/ / __ \/ __ \/ / __ \/ __ `/
 _/ // /_/ / ____/   ___/ / / / / / /_/ / /_/ / / / / / /_/ /
/___/_____/_/       /____/_/ /_/_/ .___/ .___/_/_/ /_/\__, /
                                /_/   /_/            /____/
"""
