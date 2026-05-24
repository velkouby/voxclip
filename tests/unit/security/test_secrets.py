from __future__ import annotations

from vox_voice_paste.security import OPENAI_API_KEY_SECRET, InMemorySecretService


def test_in_memory_secret_service_tracks_secret_presence() -> None:
    secrets = InMemorySecretService()

    assert secrets.get_secret(OPENAI_API_KEY_SECRET) is None

    secrets.set_secret(OPENAI_API_KEY_SECRET, "sk-test-secret")
    assert secrets.get_secret(OPENAI_API_KEY_SECRET) == "sk-test-secret"

    secrets.delete_secret(OPENAI_API_KEY_SECRET)
    assert secrets.get_secret(OPENAI_API_KEY_SECRET) is None
