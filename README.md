# shippy

`shippy` is a Python application designed to streamline the process of printing shipping labels for books destined for incarcerated individuals in Texas. It integrates with an internal server for address management and the EasyPost API for postage purchasing and label generation.

## Purpose

The primary goal of this utility is to provide a robust system for the Inside Books Project (IBP) to generate and print accurate shipping labels. It automates the postage purchasing and label creation process, interacting with IBP's internal server to retrieve recipient addresses and using EasyPost for carrier services. The application supports various shipping workflows, including bulk, individual, and manual shipments.

## About Inside Books Project

Inside Books Project is an Austin-based community service volunteer organization that sends free reading materials to people incarcerated in Texas, and also publishes resource guides and short-form instructional pamphlets. Inside Books is the only books-to-prisoners program in Texas, where more than 120,000 people are behind bars. Inside Books Project works to promote reading, literacy, and education among incarcerated individuals and to educate the general public on issues of incarceration.

## Features

- **Integration with IBP Server**: Fetches unit IDs, return addresses, and recipient addresses from an internal IBP server.
- **EasyPost API Integration**: Utilizes the EasyPost API for purchasing postage and generating shipping labels.
- **Multiple Shipping Modes**: Supports bulk, individual, and manual address input for shipping.
- **Label Printing**: Generates and prints postage labels, with an option to include a custom logo.
- **Error Handling**: Includes mechanisms to catch and display errors during the shipping process.

## Installation and Development

To set up the `shippy` project for development, ensure you have [uv](https://github.com/astral-sh/uv) installed.

1.  **Create and activate a virtual environment:**

    ```
    uv venv
    source .venv/bin/activate
    ```

    On Windows, use `.venv\Scripts\activate`.

2.  **Install dependencies:**

    The project dependencies are defined in `pyproject.toml`. Sync them using `uv`:

    ```
    uv sync --all-extras
    ```

## Configuration

The application requires a configuration file for the internal IBP server and the EasyPost API.

1.  Create a `config.ini` file.
2.  Populate it with your API keys and server URL:

    ```
    [ibp]
    url = http://your_ibp_server_url:8000
    apikey = your_ibp_api_key_here

    [easypost]
    apikey = your_easypost_api_key_here
    ```

    - `ibp.url`: The URL of your internal IBP server.
    - `ibp.apikey`: The API key for the IBP server.
    - `easypost.apikey`: Your EasyPost API key.

## Usage

The `shippy` application is run from the command line. You must specify the path to your configuration file using the `--config` option.

### Running from the Local Environment

Once you've installed the dependencies in your virtual environment, you can run the tool using `shippy` or `python -m shippy`.

```
shippy --config path/to/your/config.ini <shipping_type>
```

Replace `<shipping_type>` with one of the following commands:

- `individual`: For shipping individual packages.
- `bulk`: For shipping bulk packages.
- `manual`: For manually entering address details.

**Example:**

```
shippy --config config.ini individual
```

### Running as a Tool with `uvx`

You can also run the application directly from the git repository without a local installation using `uvx`. This is useful for running the tool in different environments.

```
uvx --from git+https://github.com/jonkensta/shippy.git@main shippy --config path/to/your/config.ini <shipping_type>
```

**Example:**

```
uvx --from git+https://github.com/jonkensta/shippy.git@main shippy --config config.ini bulk
```

To wrap the above in a powershell command, you can do the following:

```
powershell.exe -NoExit -Command "& { & 'uvx' --from 'git+https://github.com/jonkensta/shippy.git@main' 'shippy' --config 'C:\path\to\your\config.ini' 'bulk' }"
```

## Label printers

Printing is handled by the shared
[`ibp-printing`](https://github.com/jonkensta/ibp-printing) library. On Windows a
print queue is only used when **both** of these hold:

1. The queue name ends in the printer's USB `VID:PID`, separated from the rest of
   the name by a space, tab, `_` or `-` — e.g. `DYMO LabelWriter 450 0922:0028`.
   Local and connected queues are both considered.
2. A USB device with that `VID:PID` is currently plugged in.

If several queues qualify, healthy, problem-free and default queues are tried
first; if one fails before the job is spooled, the next one is tried. After
spooling, shippy follows the job for up to 30 seconds and warns if the spooler
reports an error or never finishes it (the label may not have printed; postage is
not refunded automatically in that case because it may well have printed).

On Linux, every CUPS queue is usable. For development without printing a label,
pass `--preview` to open each label in an image viewer instead:

```
shippy --preview --config config.ini manual
```

### Logs

Every discovery pass and print attempt is logged verbosely to

- Windows: `%LOCALAPPDATA%\ibp-printing\logs`
- Linux: `~/.local/state/ibp-printing/logs` (or `$XDG_STATE_HOME/ibp-printing/logs`)

`printer.log` is human-readable and `printer.jsonl` has one JSON object per line.
Collect both after any printing incident.

## Troubleshooting the label printer

If shipping fails with **"No label printer found plugged in"** even though the
printer is powered and connected, run the `diagnose-printer` command to capture a
snapshot of the printer and USB state. It needs no config file:

```
shippy diagnose-printer
```

Or via `uvx`:

```
uvx --from git+https://github.com/jonkensta/shippy.git@main shippy diagnose-printer
```

Run it **while the problem is happening** and send back the output together with
the log files above. For every print queue it reports each detection check (name
`VID:PID` suffix, USB device present and healthy, queue status) and whether the
queue would be used, followed by the USB devices Windows sees and recent
PrintService events.
