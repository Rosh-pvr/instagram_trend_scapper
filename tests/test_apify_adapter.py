from app.collectors.apify_instagram import ApifyInstagramCollector


def test_apify_row_to_hashtag_trends(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "test")
    collector = ApifyInstagramCollector({"instagram_hashtags": ["ai"]})
    rows = [
        {
            "id": "abc",
            "caption": "AI agents are moving fast #AIAgents #AI",
            "likes": 120,
            "commentsCount": 10,
            "plays": 1000,
            "timestamp": "2026-09-24T09:30:00+00:00",
            "permalink": "https://instagram.com/p/abc",
        }
    ]
    out = collector._to_trends(rows)
    assert any(x.title == "#aiagents" for x in out)
    assert any(x.title == "#ai" for x in out)
    assert out[0].engagement == 1130
