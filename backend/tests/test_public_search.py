"""Public search: provider selection, URL validation and answer parsing.

Two things are worth pinning here. The SearXNG base URL comes from operator
configuration rather than a request, but it is still the address every query
leaves through, so a typo or a stray scheme sending searches somewhere
unintended is a privacy failure rather than a bug. And the answers come from
outside, so parsing them must degrade rather than raise.

No test opens a socket: the bounded-read helper is substituted.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import public_search


def _settings(*, searxng: str = "", brave: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        searxng_url=searxng,
        brave_api_key=brave,
        max_lookup_response_bytes=5_242_880,
    )


# --- The address queries leave through ----------------------------------------


def test_the_search_path_is_appended_to_the_configured_base() -> None:
    assert public_search._searxng_search_url("https://searx.example") == "https://searx.example/search"
    assert public_search._searxng_search_url("https://searx.example/") == "https://searx.example/search"
    assert public_search._searxng_search_url("https://searx.example/sub") == "https://searx.example/sub/search"


def test_a_configured_query_or_fragment_is_discarded() -> None:
    """Only the base belongs in the request this builds.

    Carrying a configured query string through would let it merge with the
    parameters the search itself sets, and a fragment is never sent at all —
    keeping either would only make the effective URL harder to reason about.
    """
    assert (
        public_search._searxng_search_url("https://searx.example/?debug=1#frag")
        == "https://searx.example/search"
    )


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param("ftp://searx.example", id="wrong-scheme"),
        pytest.param("searx.example", id="no-scheme"),
        pytest.param("", id="empty"),
        pytest.param("https://", id="no-host"),
    ],
)
def test_a_base_that_is_not_an_http_url_is_refused(configured) -> None:
    with pytest.raises(ValueError, match="http"):
        public_search._searxng_search_url(configured)


def test_credentials_embedded_in_the_base_are_refused() -> None:
    """A URL-embedded credential would be sent with every query and logged by proxies."""
    with pytest.raises(ValueError, match="credentials"):
        public_search._searxng_search_url("https://user:secret@searx.example")


# --- Provider selection -------------------------------------------------------


@pytest.mark.asyncio
async def test_no_configured_provider_means_no_search_and_no_network(monkeypatch) -> None:
    async def must_not_be_called(client, url, **kwargs):
        raise AssertionError(f"unexpected outbound request to {url!r}")

    monkeypatch.setattr(public_search, "get_settings", lambda: _settings())
    monkeypatch.setattr(public_search, "get_json_bounded", must_not_be_called)

    assert await public_search.search_public("ada lovelace") == []


@pytest.mark.asyncio
async def test_a_searxng_failure_falls_back_to_brave(monkeypatch) -> None:
    attempted: list[str] = []

    async def fake_json(client, url, **kwargs):
        attempted.append(url)
        if "searx" in url:
            raise RuntimeError("instance unreachable")
        return {"web": {"results": [{"title": "T", "url": "https://example.test", "description": "D"}]}}

    monkeypatch.setattr(
        public_search, "get_settings", lambda: _settings(searxng="https://searx.example", brave="key")
    )
    monkeypatch.setattr(public_search, "get_json_bounded", fake_json)

    results = await public_search.search_public("ada lovelace")

    assert [r["source_name"] for r in results] == ["brave"]
    assert len(attempted) == 2 and "searx" in attempted[0]


@pytest.mark.asyncio
async def test_a_searxng_answer_with_no_results_is_an_answer(monkeypatch) -> None:
    """An empty successful search must not silently re-run against another provider.

    The operator chose SearXNG; falling through to Brave on an empty result
    would send the same query somewhere they did not pick, which is a privacy
    decision rather than a retry.
    """
    attempted: list[str] = []

    async def fake_json(client, url, **kwargs):
        attempted.append(url)
        return {"results": []}

    monkeypatch.setattr(
        public_search, "get_settings", lambda: _settings(searxng="https://searx.example", brave="key")
    )
    monkeypatch.setattr(public_search, "get_json_bounded", fake_json)

    assert await public_search.search_public("ada lovelace") == []
    assert len(attempted) == 1, "a successful empty search must not fall through"


@pytest.mark.asyncio
async def test_every_provider_failing_yields_no_results_rather_than_raising(monkeypatch) -> None:
    async def always_fails(client, url, **kwargs):
        raise RuntimeError("unreachable")

    monkeypatch.setattr(
        public_search, "get_settings", lambda: _settings(searxng="https://searx.example", brave="key")
    )
    monkeypatch.setattr(public_search, "get_json_bounded", always_fails)

    assert await public_search.search_public("ada lovelace") == []


# --- Parsing answers from outside ---------------------------------------------


@pytest.mark.asyncio
async def test_searxng_results_are_mapped_and_bounded(monkeypatch) -> None:
    async def fake_json(client, url, **kwargs):
        return {
            "results": [
                {"title": f"T{i}", "url": f"https://example.test/{i}", "content": f"C{i}", "engine": "duckduckgo"}
                for i in range(10)
            ]
        }

    monkeypatch.setattr(public_search, "get_settings", lambda: _settings(searxng="https://searx.example"))
    monkeypatch.setattr(public_search, "get_json_bounded", fake_json)

    results = await public_search.search_public("ada lovelace", max_results=3)

    assert len(results) == 3, "a generous instance must not decide how much we store"
    assert results[0] == {
        "title": "T0",
        "url": "https://example.test/0",
        "snippet": "C0",
        "source_name": "duckduckgo",
    }


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(None, id="null-body"),
        pytest.param({}, id="no-results-key"),
        pytest.param({"results": []}, id="empty-results"),
    ],
)
@pytest.mark.asyncio
async def test_a_thin_searxng_answer_yields_nothing_instead_of_raising(monkeypatch, payload) -> None:
    async def fake_json(client, url, **kwargs):
        return payload

    monkeypatch.setattr(public_search, "get_settings", lambda: _settings(searxng="https://searx.example"))
    monkeypatch.setattr(public_search, "get_json_bounded", fake_json)

    assert await public_search.search_public("ada lovelace") == []


@pytest.mark.asyncio
async def test_brave_results_are_read_from_their_nested_shape(monkeypatch) -> None:
    async def fake_json(client, url, **kwargs):
        return {
            "web": {
                "results": [
                    {"title": "Result", "url": "https://example.test/a", "description": "Snippet"},
                    {"title": "Second", "url": "https://example.test/b"},
                ]
            }
        }

    monkeypatch.setattr(public_search, "get_settings", lambda: _settings(brave="key"))
    monkeypatch.setattr(public_search, "get_json_bounded", fake_json)

    results = await public_search.search_public("ada lovelace")

    assert [r["url"] for r in results] == ["https://example.test/a", "https://example.test/b"]
    assert results[1]["snippet"] == "", "a missing field is empty, not an error"
    assert {r["source_name"] for r in results} == {"brave"}


@pytest.mark.asyncio
async def test_the_brave_key_travels_in_the_header_and_never_in_the_query(monkeypatch) -> None:
    """A key in a query string lands in proxy logs and browser history."""
    captured: dict = {}

    async def fake_json(client, url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return {"web": {"results": []}}

    monkeypatch.setattr(public_search, "get_settings", lambda: _settings(brave="super-secret"))
    monkeypatch.setattr(public_search, "get_json_bounded", fake_json)

    await public_search.search_public("ada lovelace")

    assert captured["headers"]["X-Subscription-Token"] == "super-secret"
    assert "super-secret" not in captured["url"]
    assert "super-secret" not in str(captured["params"])
