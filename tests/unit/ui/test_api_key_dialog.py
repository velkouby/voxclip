from __future__ import annotations

from vox_voice_paste.security import (
    OPENAI_API_KEY_SECRET,
    SONIOX_API_KEY_SECRET,
    InMemorySecretService,
    KeyValidationResult,
    StaticOpenAIKeyValidator,
)
from vox_voice_paste.ui.api_key_dialog import OpenAIKeyDialog


def test_openai_key_dialog_stores_valid_key(qtbot) -> None:
    secrets = InMemorySecretService()
    dialog = OpenAIKeyDialog(
        secret_service=secrets,
        key_validator=StaticOpenAIKeyValidator(),
    )
    qtbot.addWidget(dialog)

    dialog.key_input.setText("sk-test-secret")
    dialog.save_key()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert secrets.get_secret(OPENAI_API_KEY_SECRET) == "sk-test-secret"
    assert dialog.key_input.text() == ""


def test_openai_key_dialog_does_not_store_invalid_key(qtbot) -> None:
    secrets = InMemorySecretService()
    dialog = OpenAIKeyDialog(
        secret_service=secrets,
        key_validator=StaticOpenAIKeyValidator(KeyValidationResult(False, "Invalid key.")),
    )
    qtbot.addWidget(dialog)

    dialog.key_input.setText("sk-test-secret")
    dialog.save_key()

    assert dialog.result() == dialog.DialogCode.Rejected
    assert secrets.get_secret(OPENAI_API_KEY_SECRET) is None
    assert "Invalid key" in dialog.status_label.text()


def test_api_key_dialog_can_store_soniox_key(qtbot) -> None:
    secrets = InMemorySecretService()
    dialog = OpenAIKeyDialog(
        secret_service=secrets,
        key_validator=StaticOpenAIKeyValidator(),
        secret_name=SONIOX_API_KEY_SECRET,
        service_name="Soniox",
    )
    qtbot.addWidget(dialog)

    dialog.key_input.setText("soniox-test-secret")
    dialog.save_key()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert secrets.get_secret(SONIOX_API_KEY_SECRET) == "soniox-test-secret"
