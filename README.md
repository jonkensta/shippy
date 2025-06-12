# shippy

`shippy` is a Python application designed to streamline the process of printing shipping labels for books destined for incarcerated individuals in Texas. It integrates with an internal server for address management and the EasyPost API for postage purchasing and label generation.

## Purpose

The primary goal of this utility is to provide a robust system for the Inside Books Project (IBP) to generate and print accurate shipping labels.
It automates the postage purchasing and label creation process,
interacting with IBP's internal server to retrieve recipient addresses and using EasyPost for carrier services.
The application supports various shipping workflows, including bulk, individual, and manual shipments.

## About Inside Books Project

Inside Books Project is an Austin-based community service volunteer organization that sends free reading materials to people incarcerated in Texas, and
also publishes resource guides and short-form instructional pamphlets.
Inside Books is the only books-to-prisoners program in Texas, where more than 120,000 people are behind bars.
Inside Books Project works
    to promote reading, literacy, and education among incarcerated individuals and
    to educate the general public on issues of incarceration.

## Features

- **Integration with IBP Server**: Fetches unit IDs, return addresses, and recipient addresses from an internal IBP server.
- **EasyPost API Integration**: Utilizes the EasyPost API for purchasing postage and generating shipping labels.
- **Multiple Shipping Modes**: Supports bulk, individual, and manual address input for shipping.
- **Label Printing**: Generates and prints postage labels, with an option to include a custom logo.
- **Error Handling**: Includes mechanisms to catch and display errors during the shipping process.

## Installation

To set up the `shippy` project, ensure you have Python 3.11 installed. You can install the necessary dependencies using `pip`:

1.  **Create a virtual environment (recommended):**

    ```bash
    python -m venv venv
    ```

2.  **Activate the virtual environment:**

    - **On Windows:**
      ```bash
      .\venv\Scripts\activate
      ```
    - **On macOS/Linux:**
      ```bash
      source venv/bin/activate
      ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    If you are on Windows, you may also need to install `pywin32`:
    ```bash
    pip install -r requirements_win.txt
    ```

## Configuration

The application requires configuration details for the internal IBP server and the EasyPost API.
These are set in the `shippy/config.ini` file:

```ini
[DEFAULT]
testing = 1

[ibp]
url = http://localhost:8000
logo = logo.jpg
apikey = your_ibp_api_key_here

[easypost]
apikey = your_easypost_api_key_here
```

- `ibp.url`: Set this to the URL of your internal IBP server.
- `ibp.apikey`: Provide your API key for the IBP server.
- `easypost.apikey`: Enter your EasyPost API key here.

## Usage

The `shippy` application can be run directly from the command line,
with different options for bulk, individual, or manual shipping.

### Running from `__main__.py`

You can use the main entry point to select the shipping type:

```bash
python -m shippy <shipping_type>
```

Replace `<shipping_type>` with one of the following:

- `individual`: For shipping individual packages.
- `bulk`: For shipping bulk packages.
- `manual`: For manually entering address details.

**Example:**

```bash
python -m shippy individual
```

### Running with specific scripts

Alternatively, you can run the dedicated scripts for each shipping type located in the `scripts` directory:

- **Bulk Shipping:**

  ```bash
  python scripts/bulk.py
  ```

- **Individual Shipping:**

  ```bash
  python scripts/individual.py
  ```

- **Manual Shipping:**
  ```bash
  python scripts/manual.py
  ```

### PyInstaller

The project also supports building single-file executables using PyInstaller for easier distribution.
The following commands can be run from the root project directory:

```bash
pyinstaller --onefile --console --paths . --icon "shippy/logo.jpg" --add-data "shippy/logo.jpg;shippy" --add-data "shippy/config.ini;shippy" --name "SHIP BULK" "./scripts/bulk.py"
```

```bash
pyinstaller --onefile --console --paths . --icon "shippy/logo.jpg" --add-data "shippy/logo.jpg;shippy" --add-data "shippy/config.ini;shippy" --name "SHIP INDIVIDUAL" "./scripts/individual.py"
```

```bash
pyinstaller --onefile --console --paths . --icon "shippy/logo.jpg" --add-data "shippy/logo.jpg;shippy" --add-data "shippy/config.ini;shippy" --name "SHIP MANUAL" "./scripts/manual.py"
```
