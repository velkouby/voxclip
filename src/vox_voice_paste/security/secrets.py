from __future__ import annotations

from typing import Protocol

import keyring

KEYRING_SERVICE_NAME = "vox-voice-paste"
OPENAI_API_KEY_SECRET = "openai-api-key"


class SecretError(RuntimeError):
    """Raised when the configured secret backend is unavailable or fails."""


class SecretService(Protocol):
    def get_secret(self, name: str) -> str | None: ...

    def set_secret(self, name: str, value: str) -> None: ...

    def delete_secret(self, name: str) -> None: ...


class KeyringSecretService:
    def __init__(self, service_name: str = KEYRING_SERVICE_NAME) -> None:
        self._service_name = service_name

    def get_secret(self, name: str) -> str | None:
        try:
            return keyring.get_password(self._service_name, name)
        except Exception as exc:
            raise SecretError("Secret backend is unavailable") from exc

    def set_secret(self, name: str, value: str) -> None:
        try:
            keyring.set_password(self._service_name, name, value)
        except Exception as exc:
            raise SecretError("Secret backend is unavailable") from exc

    def delete_secret(self, name: str) -> None:
        try:
            keyring.delete_password(self._service_name, name)
        except keyring.errors.PasswordDeleteError:
            return
        except Exception as exc:
            raise SecretError("Secret backend is unavailable") from exc


class InMemorySecretService:
    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._secrets = dict(initial or {})

    def get_secret(self, name: str) -> str | None:
        return self._secrets.get(name)

    def set_secret(self, name: str, value: str) -> None:
        self._secrets[name] = value

    def delete_secret(self, name: str) -> None:
        self._secrets.pop(name, None)
