from sahifa.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("SAHIFA_BOT_TOKEN", "x")
    monkeypatch.setenv("SAHIFA_ADMIN_IDS", "[1,2]")
    monkeypatch.setenv("SAHIFA_ADMIN_CHAT_ID", "-100")
    settings = Settings(_env_file=None)
    assert settings.bot_token == "x"
    assert settings.admin_ids == [1, 2]
    assert settings.admin_chat_id == -100
