import os

from secret_store import LocalSecretStore, restore_telegram_credentials


def test_secret_store_round_trip_without_plaintext(tmp_path, monkeypatch):
    monkeypatch.setattr("secret_store._protect", lambda value: b"encrypted:" + value[::-1])
    monkeypatch.setattr("secret_store._unprotect", lambda value: value.removeprefix(b"encrypted:")[::-1])
    path = tmp_path / "credentials.bin"
    store = LocalSecretStore(path)
    store.save({"TELEGRAM_BOT_TOKEN": "private-token", "TELEGRAM_CHAT_ID": "private-chat"})
    raw = path.read_bytes()
    assert b"private-token" not in raw
    assert b"private-chat" not in raw
    assert store.load()["TELEGRAM_BOT_TOKEN"] == "private-token"


def test_restore_does_not_override_explicit_environment(tmp_path, monkeypatch):
    monkeypatch.setattr("secret_store._protect", lambda value: value)
    monkeypatch.setattr("secret_store._unprotect", lambda value: value)
    store = LocalSecretStore(tmp_path / "credentials.bin")
    store.save({"TELEGRAM_BOT_TOKEN": "stored-token", "TELEGRAM_CHAT_ID": "stored-chat"})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "explicit-token")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert restore_telegram_credentials(store) is True
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "explicit-token"
    assert os.environ["TELEGRAM_CHAT_ID"] == "stored-chat"


def test_missing_or_corrupt_vault_fails_closed(tmp_path, monkeypatch):
    store = LocalSecretStore(tmp_path / "credentials.bin")
    assert store.load() == {}
    store.path.write_bytes(b"corrupt")
    monkeypatch.setattr("secret_store._unprotect", lambda value: (_ for _ in ()).throw(ValueError("bad")))
    assert store.load() == {}
