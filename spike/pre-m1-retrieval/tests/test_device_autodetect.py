"""Verify the spike-1 server's device-autodetect helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "server_stdio",
    Path(__file__).resolve().parent.parent / "server-stdio.py",
)
server_stdio = importlib.util.module_from_spec(_spec)
sys.modules["server_stdio"] = server_stdio
_spec.loader.exec_module(server_stdio)


def test_select_device_returns_valid_string():
    """select_device returns 'cuda' or 'cpu', never None or anything else."""
    device = server_stdio.select_device()
    assert device in ("cuda", "cpu"), f"unexpected device: {device!r}"


def test_select_device_matches_torch_availability():
    """select_device returns 'cuda' iff torch reports CUDA available."""
    import torch

    expected = "cuda" if torch.cuda.is_available() else "cpu"
    assert server_stdio.select_device() == expected
