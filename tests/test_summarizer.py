from app.models import TrendItem
from app.summarizer import summarize


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Gemini report"}}]}


def test_summarize_uses_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr("app.summarizer.requests.post", fake_post)

    out = summarize([
        TrendItem(
            title="#ai",
            source="Instagram via Apify",
            keyword="#ai",
            url="https://instagram.com/p/test",
            engagement=100,
            metadata={"score": 0.8, "velocity": 0.7, "caption": "AI is trending"},
        )
    ])

    assert out == "Gemini report"
    assert seen["url"].endswith("/chat/completions")
    assert seen["kwargs"]["json"]["model"] == "gemini-3.8-flash"
    assert seen["kwargs"]["headers"]["Authorization"] == "Bearer secret"
