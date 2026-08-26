from brokers import zerodha


class FakeKite:
    def __init__(self, api_key):
        self.api_key = api_key

    def login_url(self):
        return f"https://kite.test/login?api_key={self.api_key}"

    def generate_session(self, request_token, api_secret):
        assert request_token == "one-time-token"
        assert api_secret == "secret"
        return {"access_token": "daily-access-token"}


def test_kite_daily_auth_stays_in_process_memory(monkeypatch):
    monkeypatch.setattr(zerodha, "KITE_AVAILABLE", True)
    monkeypatch.setattr(zerodha, "KiteConnect", FakeKite)
    monkeypatch.setenv("KITE_API_KEY", zerodha.KITE_API_KEY)
    monkeypatch.setenv("KITE_API_SECRET", zerodha.KITE_API_SECRET)
    monkeypatch.setenv("KITE_ACCESS_TOKEN", zerodha.KITE_ACCESS_TOKEN)

    start = zerodha.begin_auth("key", "secret")
    assert start["login_url"].endswith("api_key=key")
    assert start["storage"] == "PROCESS_MEMORY_ONLY"
    assert not zerodha.KITE_ACCESS_TOKEN

    completed = zerodha.complete_auth("one-time-token")
    assert completed == {"authenticated": True, "storage": "PROCESS_MEMORY_ONLY"}
    assert zerodha.KITE_ACCESS_TOKEN == "daily-access-token"
    assert zerodha.is_configured() is True


def test_kite_auth_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr(zerodha, "KITE_AVAILABLE", True)
    try:
        zerodha.begin_auth("", "")
    except ValueError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("missing credentials must fail")
