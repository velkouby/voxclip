from __future__ import annotations

from vox_voice_paste.desktop import InMemoryNotificationService


def test_in_memory_notifications_store_title_and_body() -> None:
    notifications = InMemoryNotificationService()

    notifications.notify("Title", "Body")

    assert notifications.notifications[0].title == "Title"
    assert notifications.notifications[0].body == "Body"
