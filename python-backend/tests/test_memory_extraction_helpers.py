from types import SimpleNamespace

from app.routers.user_memory import _summarize_memory_text


def test_summarize_memory_text_prefers_first_user_message():
    title, summary = _summarize_memory_text(
        [
            SimpleNamespace(role="system", content="setup"),
            SimpleNamespace(role="user", content="Remember that I prefer concise updates."),
            SimpleNamespace(role="assistant", content="Got it."),
        ]
    )

    assert title == "Remember that I prefer concise updates."
    assert "assistant: Got it." in summary
