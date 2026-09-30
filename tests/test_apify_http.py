from app.collectors.apify_instagram import ApifyInstagramCollector


class FakeResponse:
    ok = True
    status_code = 200
    text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return [{
            "id": "1",
            "caption": "hello #AI",
            "likes": 1,
            "commentsCount": 2,
            "timestamp": "2026-09-24T10:00:00+00:00",
            "url": "https://instagram.com/p/1",
        }]


def test_apify_http_request(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "secret")
    collector = ApifyInstagramCollector({"instagram_hashtags": ["ai"], "apify_results_limit": 5})
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr("app.collectors.apify_instagram.requests.post", fake_post)
    out = collector.collect()

    assert "apify~instagram-hashtag-scraper" in seen["url"]
    assert seen["kwargs"]["json"]["hashtags"] == ["ai"]
    assert seen["kwargs"]["json"]["resultsLimit"] == 5
    assert out and out[0].title == "#ai"
