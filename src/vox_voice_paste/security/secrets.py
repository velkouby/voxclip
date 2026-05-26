# SPDX-FileCopyrightText: 2026 VoxClip contributors
# SPDX-License-Identifier: MIT
# Author: Vincent Elkouby
# Contact: https://github.com/velkouby

import contextlib
from typing import Protocol

import keyring

KEYRING_SERVICE_NAME = "voxclip"
LEGACY_KEYRING_SERVICE_NAMES = ("vox-voice-paste",)
OPENAI_API_KEY_SECRET = "openai-api-key"
SONIOX_API_KEY_SECRET = "soniox-api-key"


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
            value = keyring.get_password(self._service_name, name)
            if value is not None or self._service_name != KEYRING_SERVICE_NAME:
                return value

            for legacy_service_name in LEGACY_KEYRING_SERVICE_NAMES:
                value = keyring.get_password(legacy_service_name, name)
                if value is None:
                    continue
                with contextlib.suppress(Exception):
                    keyring.set_password(self._service_name, name, value)
                return value
            return None
        except Exception as exc:
            raise SecretError("Secret backend is unavailable") from exc

    def set_secret(self, name: str, value: str) -> None:
        try:
            keyring.set_password(self._service_name, name, value)
        except Exception as exc:
            raise SecretError("Secret backend is unavailable") from exc

    def delete_secret(self, name: str) -> None:
        service_names = [self._service_name]
        if self._service_name == KEYRING_SERVICE_NAME:
            service_names.extend(LEGACY_KEYRING_SERVICE_NAMES)
        failures = []
        for service_name in service_names:
            try:
                keyring.delete_password(service_name, name)
            except keyring.errors.PasswordDeleteError:
                continue
            except Exception as exc:
                failures.append(exc)
        if failures:
            raise SecretError("Secret backend is unavailable") from failures[0]

class InMemorySecretService:
    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._secrets = dict(initial or {})

    def get_secret(self, name: str) -> str | None:
        return self._secrets.get(name)

    def set_secret(self, name: str, value: str) -> None:
        self._secrets[name] = value

    def delete_secret(self, name: str) -> None:
        self._secrets.pop(name, None)
