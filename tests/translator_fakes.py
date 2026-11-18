"""Stand-ins for the HTTP layer.

The app's translator runs locally and makes no requests; what still talks
HTTP is the MyMemory engine in tools/compare_translators.py. A fake session
that hands back queued responses is all its test needs.
"""

from __future__ import annotations


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, raises_json: bool = False) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._raises_json = raises_json

    def json(self):
        if self._raises_json:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Answers requests from a scripted queue, remembering what it was asked."""

    def __init__(self) -> None:
        self.verify = True
        self.calls: list[dict] = []
        self._script: dict[str, list] = {}

    def script(self, url: str, *responses) -> None:
        self._script[url] = list(responses)

    def _answer(self, method: str, url: str, **kwargs):
        # `session_verify` is captured per call, not read at the end: a backend
        # that switched verification off for a retry and set it back would be
        # invisible to a check made after the fact.
        self.calls.append({"method": method, "url": url, "session_verify": self.verify, **kwargs})
        queue = self._script.get(url)
        if not queue:
            raise AssertionError(f"unscripted {method} to {url}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url, **kwargs):
        return self._answer("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self._answer("GET", url, **kwargs)
