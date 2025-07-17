"""Test for autocompleting an address input."""

import os
import sys

import googlemaps
import questionary
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

# --- Step 1: Set up the Google Maps client ---
# It's best practice to use environment variables for API keys.
api_key = os.getenv("Maps_API_KEY")
if not api_key:
    print("Error: Maps_API_KEY environment variable not set.")
    sys.exit()

gmaps = googlemaps.Client(key=api_key)


# --- Step 2: Create a custom completer for Google Maps ---
class GoogleMapsCompleter(Completer):
    """Custom completer that fetches suggestions from the Google Maps Places API."""

    def get_completions(self, document: Document, complete_event):
        """This method is called by prompt_toolkit on every key press."""
        text_before_cursor = document.text_before_cursor

        # Only start searching after 3 characters to save on API calls
        if len(text_before_cursor) < 3:
            return

        try:
            # Call the Google Maps Places Autocomplete API
            autocomplete_result = gmaps.places_autocomplete(
                input_text=text_before_cursor,
                components={"country": "US"},  # Restrict to US addresses
            )

            # Yield a Completion object for each prediction
            for prediction in autocomplete_result:
                yield Completion(
                    text=prediction["description"],
                    start_position=-len(
                        text_before_cursor
                    ),  # Replaces the text being typed
                )
        except Exception:
            pass


def ask_for_address():
    """Prompts the user for an address using the custom completer."""
    print("Start typing a US address (e.g., '1600 Amphitheatre')...")

    selected_address = questionary.autocomplete(
        "Enter a US address:",
        choices=[],
        completer=GoogleMapsCompleter(),
        validate=lambda text: True if len(text) > 0 else "Please enter an address.",
    ).ask()

    if selected_address:
        print(f"\n✅ You selected: {selected_address}")
    else:
        print("\n❌ No address selected.")
