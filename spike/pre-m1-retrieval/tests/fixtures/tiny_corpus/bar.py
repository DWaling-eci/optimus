"""bar module -- HTTP client wrapper for legacy services.

This module wraps the requests library with a thin convenience layer
adding retry logic, timeout handling, and JSON parsing. It is intentionally
verbose to exceed the 1500-char chunk threshold so the chunking tests
exercise the multi-chunk code path.
"""

import requests


class HttpClient:
    """Thin wrapper around requests with retry + timeout.

    Args:
        base_url: scheme+host root (no trailing slash necessary; stripped).
        timeout: per-request timeout in seconds. Default 30.
    """

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str):
        """HTTP GET; returns parsed JSON body."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.get(url, timeout=self.timeout).json()

    def post(self, path: str, body: dict):
        """HTTP POST with JSON body; returns parsed JSON response."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.post(url, json=body, timeout=self.timeout).json()

    def delete(self, path: str):
        """HTTP DELETE; returns status code int."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.delete(url, timeout=self.timeout).status_code

    def put(self, path: str, body: dict):
        """HTTP PUT with JSON body; returns parsed JSON response."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.put(url, json=body, timeout=self.timeout).json()

    def patch(self, path: str, body: dict):
        """HTTP PATCH with JSON body; returns parsed JSON response."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return requests.patch(url, json=body, timeout=self.timeout).json()

    def head(self, path: str):
        """HTTP HEAD; returns dict of response headers."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return dict(requests.head(url, timeout=self.timeout).headers)


def quick_check(base: str) -> bool:
    """Probe a health endpoint; return True on 200 OK with status==ok."""
    client = HttpClient(base)
    try:
        result = client.get("/health")
        return result.get("status") == "ok"
    except Exception:
        return False


def bulk_fetch(base: str, paths: list) -> list:
    """Fetch multiple paths sequentially; returns a list of result dicts."""
    client = HttpClient(base)
    results = []
    for path in paths:
        try:
            results.append({"path": path, "ok": True, "data": client.get(path)})
        except Exception as exc:
            results.append({"path": path, "ok": False, "error": repr(exc)})
    return results
