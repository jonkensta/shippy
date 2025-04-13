# shippy

IBP shipping application through easypost

## PyInstaller

The main entry points to running `shippy` are in the `scripts` folder.
To build all of the single-file executables, run the following in the root project directory:

```bash
pyinstaller --onefile --console --paths .
    --icon "shippy/logo.jpg" --add-data "shippy/logo.jpg;shippy" --add-data "shippy/config.ini;shippy"
    --name "SHIP BULK" "./scripts/bulk.py"
```

```bash
pyinstaller --onefile --console --paths .
    --icon "shippy/logo.jpg" --add-data "shippy/logo.jpg;shippy" --add-data "shippy/config.ini;shippy"
    --name "SHIP INDIVIDUAL" "./scripts/individual.py"
```

```bash
pyinstaller --onefile --console --paths .
    --icon "shippy/logo.jpg" --add-data "shippy/logo.jpg;shippy" --add-data "shippy/config.ini;shippy"
    --name "SHIP MANUAL" "./scripts/manual.py"
```
