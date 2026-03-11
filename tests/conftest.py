# Shared pytest fixtures.
#
# On Windows the default pytest tmp_path can hit permission errors on
# the system temp dir.  We override it to use a project-local directory.

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path(tmp_path_factory):
    """Override tmp_path to use a project-local temp folder on Windows."""
    base = Path(__file__).parent.parent / ".pytest_tmp"
    base.mkdir(exist_ok=True)
    d = tempfile.mkdtemp(dir=base)
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)
