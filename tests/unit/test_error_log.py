from __future__ import annotations

import json

from vox_voice_paste.error_log import (
    default_error_log_path,
    read_error_log_tail,
    record_error,
)


def test_default_error_log_path_uses_user_state_path(monkeypatch, tmp_path) -> None:
    def fake_user_state_path(app_id: str, *, appauthor: bool = False):
        assert app_id == "voxclip"
        assert appauthor is False
        return tmp_path / app_id

    monkeypatch.setattr("vox_voice_paste.error_log.user_state_path", fake_user_state_path)

    assert default_error_log_path() == tmp_path / "voxclip" / "errors.log"


def test_record_error_writes_jsonl_with_sanitized_context(tmp_path) -> None:
    log_path = tmp_path / "errors.log"

    record_error(
        event="transcription_failed",
        component="test",
        message="failed with Bearer sk-test-secret",
        context={
            "api_key": "soniox-test-secret",
            "Authorization": "Bearer soniox-test-secret",
            "transcription_model": "gpt-realtime-whisper",
            "transcript": "bonjour monde",
            "final_text": "bonjour monde",
            "audio": b"abc",
            "request_config": {
                "audio_format": "pcm_s16le",
                "model": "stt-rt-v5",
            },
        },
        log_path=log_path,
    )

    raw_log = log_path.read_text(encoding="utf-8")
    entry = json.loads(raw_log)

    assert entry["event"] == "transcription_failed"
    assert entry["level"] == "ERROR"
    assert entry["context"]["transcription_model"] == "gpt-realtime-whisper"
    assert entry["context"]["request_config"]["audio_format"] == "pcm_s16le"
    assert "soniox-test-secret" not in raw_log
    assert "sk-test-secret" not in raw_log
    assert "bonjour monde" not in raw_log
    assert "abc" not in raw_log


def test_record_error_rotates_existing_log(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "errors.log"
    log_path.write_text("x" * 100, encoding="utf-8")
    monkeypatch.setattr("vox_voice_paste.error_log.ERROR_LOG_MAX_BYTES", 100)

    record_error(
        event="failed",
        component="test",
        message="failure",
        log_path=log_path,
    )

    assert (tmp_path / "errors.log.1").exists()
    assert "failure" in log_path.read_text(encoding="utf-8")


def test_read_error_log_tail_returns_recent_lines(tmp_path) -> None:
    log_path = tmp_path / "errors.log"
    log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert read_error_log_tail(path=log_path, line_count=2) == "two\nthree"
