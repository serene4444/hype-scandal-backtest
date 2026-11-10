from app.settings import load_env


def test_load_env_skips_blanks_and_keeps_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=\nHS_TEST_NEW=from-file\nHS_TEST_SET=from-file\n")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HS_TEST_NEW", raising=False)
    monkeypatch.setenv("HS_TEST_SET", "from-shell")

    load_env(env)

    import os

    assert "ANTHROPIC_API_KEY" not in os.environ
    assert os.environ["HS_TEST_NEW"] == "from-file"
    assert os.environ["HS_TEST_SET"] == "from-shell"
    monkeypatch.delenv("HS_TEST_NEW")


def test_missing_file_is_fine(tmp_path):
    load_env(tmp_path / "nope.env")
