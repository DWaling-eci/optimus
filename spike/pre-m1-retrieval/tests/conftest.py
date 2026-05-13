"""Spike-1 pytest shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tiny_corpus() -> Path:
    """Path to the bundled tiny_corpus fixture tree."""
    return Path(__file__).parent / "fixtures" / "tiny_corpus"
