from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class KeyValidationResult:
    ok: bool
    message: str


class OpenAIKeyValidator(Protocol):
    def validate(self, api_key: str) -> KeyValidationResult: ...


class OpenAIHTTPKeyValidator:
    def __init__(self, *, timeout_seconds: float = 10.0) -> None:
        self._timeout_seconds = timeout_seconds

    def validate(self, api_key: str) -> KeyValidationResult:
        request = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                return KeyValidationResult(False, "Invalid OpenAI API key.")
            return KeyValidationResult(False, "OpenAI refused the connection test.")
        except (OSError, TimeoutError, json.JSONDecodeError):
            return KeyValidationResult(False, "Unable to connect to OpenAI.")
        return KeyValidationResult(True, "OpenAI connection verified.")


class StaticOpenAIKeyValidator:
    def __init__(self, result: KeyValidationResult | None = None) -> None:
        self._result = result or KeyValidationResult(True, "OpenAI connection verified.")

    def validate(self, api_key: str) -> KeyValidationResult:
        return self._result
