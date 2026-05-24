from __future__ import annotations

from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    InMemorySecretService,
    KeyringSecretService,
)


def test_in_memory_secret_service_tracks_secret_presence() -> None:
    secrets = InMemorySecretService()

    assert secrets.get_secret(OPENAI_API_KEY_SECRET) is None

    secrets.set_secret(OPENAI_API_KEY_SECRET, "sk-test-secret")
    assert secrets.get_secret(OPENAI_API_KEY_SECRET) == "sk-test-secret"

    secrets.delete_secret(OPENAI_API_KEY_SECRET)
    assert secrets.get_secret(OPENAI_API_KEY_SECRET) is None


def test_keyring_secret_service_migrates_legacy_service(monkeypatch) -> None:
    store = {("vox-voice-paste", OPENAI_API_KEY_SECRET): "sk-legacy"}

    def fake_get_password(service_name: str, name: str) -> str | None:
        return store.get((service_name, name))

    def fake_set_password(service_name: str, name: str, value: str) -> None:
        store[(service_name, name)] = value

    monkeypatch.setattr("vox_voice_paste.security.secrets.keyring.get_password", fake_get_password)
    monkeypatch.setattr("vox_voice_paste.security.secrets.keyring.set_password", fake_set_password)

    secrets = KeyringSecretService()

    assert secrets.get_secret(OPENAI_API_KEY_SECRET) == "sk-legacy"
    assert store[("voxclip", OPENAI_API_KEY_SECRET)] == "sk-legacy"
