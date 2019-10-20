"""
Printing implementation for different systems.
"""

# pylint: disable=unused-import
try:
    from .win32 import print_image

except ModuleNotFoundError:
    from .nosys import print_image  # type: ignore
