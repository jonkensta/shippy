"""Tests for the tempfile helper's acquisition and cleanup."""

import os
from unittest.mock import patch

import pytest

from shippy.misc import build_tempfile


def test_removes_the_file_on_the_success_path():
    with build_tempfile(suffix=".png") as tmpfile:
        path = tmpfile.name
        assert os.path.exists(path)
    assert not os.path.exists(path)


def test_creation_failure_surfaces_the_real_error():
    """Cleanup must not mask why the tempfile could not be created."""
    with patch(
        "shippy.misc.tempfile.NamedTemporaryFile",
        side_effect=PermissionError("no write access to temp dir"),
    ):
        with pytest.raises(PermissionError):
            with build_tempfile(suffix=".png"):
                pytest.fail("body must not run when creation fails")
