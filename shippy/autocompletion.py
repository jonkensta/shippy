"""Autocompletion for questionary."""

import os
import sys
import threading
import time

import googlemaps  # type: ignore
import questionary
from prompt_toolkit.completion import Completer, Completion, ThreadedCompleter
from prompt_toolkit.document import Document


class GoogleMapsCompleter(Completer):
    """Address completer that uses Google Maps."""

    gmaps: googlemaps.Client
    cache: dict[str, list[Completion]]
    debounce_delay: float
    latest_text: str
    lock: threading.Lock

    def __init__(self, gmaps: googlemaps.Client, debounce_delay: float = 2.0):
        self.gmaps = gmaps
        self.cache = {}
        self.debounce_delay = float(debounce_delay)
        self.latest_text = ""
        self.lock = threading.Lock()
        super().__init__()

    def get_completions(self, document: Document, complete_event):
        """Get address completions."""
        self.latest_text = text = document.text_before_cursor
        time.sleep(self.debounce_delay)

        # After sleeping, check if a newer keystroke has changed the desired text.
        # If so, this thread is outdated and should abort.
        if self.latest_text != text:
            return

        if len(text) < 3:
            return

        with self.lock:
            if text in self.cache:
                predictions = self.cache[text]

            else:
                try:
                    places_autocomplete = self.gmaps.places_autocomplete(
                        input_text=text, components={"country": "US"}
                    )
                except (
                    googlemaps.exceptions.ApiError,
                    googlemaps.exceptions.Timeout,
                    googlemaps.exceptions.TransportError,
                ):
                    places_autocomplete = []

                predictions = [
                    Completion(
                        text=prediction["description"], start_position=-len(text)
                    )
                    for prediction in places_autocomplete
                ]

                self.cache[text] = predictions

        yield from predictions


def demo():
    """Prompts the user for an address using the custom completer."""

    api_key = os.getenv("Maps_API_KEY")
    if not api_key:
        print("Error: Maps_API_KEY environment variable not set.")
        sys.exit()

    gmaps = googlemaps.Client(key=api_key)
    gmaps_completer = GoogleMapsCompleter(gmaps)
    threaded_completer = ThreadedCompleter(gmaps_completer)

    print("Start typing a US address (e.g., '1600 Amphitheatre')...")
    selected_address = questionary.autocomplete(
        "Enter a US address:",
        choices=[],
        completer=threaded_completer,
        validate=lambda text: True if len(text) > 0 else "Please enter an address.",
    ).ask()

    if selected_address:
        print(f"\n✅ You selected: {selected_address}")
    else:
        print("\n❌ No address selected.")
