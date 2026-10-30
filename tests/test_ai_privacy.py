"""Provider failures retain useful status without echoing credentials or private text."""

import traceback

import httpx
import pytest

from addteam import ai

SECRET = "FICTIONAL_PROVIDER_CREDENTIAL_SENTINEL"
PRIVATE_TEXT = "FICTIONAL_PRIVATE_RESPONSE_SENTINEL"
QUERY_TEXT = "FICTIONAL_URL_QUERY_SENTINEL"


def assert_safe(error):
    diagnostic = str(error) + "\n" + "".join(traceback.format_exception(error))
    for value in [SECRET, PRIVATE_TEXT, QUERY_TEXT, "https://"]:
        assert value not in diagnostic
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_google_key_is_only_in_auth_header():
    cfg = ai._AI_PROVIDERS["google"]
    url, headers, payload = ai._ai_request(cfg, SECRET, "Fictional request")
    assert url == cfg["url"]
    assert "?" not in url and SECRET not in url
    assert headers["x-goog-api-key"] == SECRET
    assert payload["contents"][0]["parts"][0]["text"] == "Fictional request"


@pytest.mark.parametrize("provider", ai.AUTO_PROVIDER_ORDER)
@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_failure_suppresses_body_url_and_exception(monkeypatch, provider, status):
    url, headers, payload = ai._ai_request(ai._AI_PROVIDERS[provider], SECRET, PRIVATE_TEXT)
    url += "?private=" + QUERY_TEXT
    request = httpx.Request("POST", url, headers=headers)
    response = httpx.Response(status, request=request, text=PRIVATE_TEXT + SECRET)
    monkeypatch.setattr(ai.httpx, "post", lambda *args, **kwargs: response)
    with pytest.raises(RuntimeError, match=f"HTTP {status}") as raised:
        ai._http_post_json(url, headers=headers, payload=payload)
    assert_safe(raised.value)


@pytest.mark.parametrize("provider", ai.AUTO_PROVIDER_ORDER)
def test_network_failure_suppresses_raw_exception(monkeypatch, provider):
    url, headers, payload = ai._ai_request(ai._AI_PROVIDERS[provider], SECRET, PRIVATE_TEXT)
    request = httpx.Request("POST", url + "?private=" + QUERY_TEXT, headers=headers)

    def fail(*args, **kwargs):
        raise httpx.ConnectError(SECRET + PRIVATE_TEXT + str(request.url), request=request)

    monkeypatch.setattr(ai.httpx, "post", fail)
    with pytest.raises(RuntimeError, match="network error") as raised:
        ai._http_post_json(str(request.url), headers=headers, payload=payload)
    assert_safe(raised.value)


@pytest.mark.parametrize("provider", ai.AUTO_PROVIDER_ORDER)
@pytest.mark.parametrize("body", [(PRIVATE_TEXT + SECRET).encode(), b"\xff" + SECRET.encode()])
def test_invalid_json_suppresses_response_body(monkeypatch, provider, body):
    url, headers, payload = ai._ai_request(ai._AI_PROVIDERS[provider], SECRET, PRIVATE_TEXT)
    request = httpx.Request("POST", url + "?private=" + QUERY_TEXT, headers=headers)
    response = httpx.Response(200, request=request, content=body)
    monkeypatch.setattr(ai.httpx, "post", lambda *args, **kwargs: response)
    with pytest.raises(RuntimeError, match="invalid JSON") as raised:
        ai._http_post_json(str(request.url), headers=headers, payload=payload)
    assert_safe(raised.value)


@pytest.mark.parametrize("provider", ai.AUTO_PROVIDER_ORDER)
@pytest.mark.parametrize("body", [{"echo": PRIVATE_TEXT + SECRET}, None, []])
def test_unexpected_provider_schema_does_not_echo_response(provider, body):
    with pytest.raises(RuntimeError, match="unexpected response format") as raised:
        ai._ai_extract(ai._AI_PROVIDERS[provider], body)
    assert_safe(raised.value)


def test_fallback_notes_retain_provider_and_status_only(monkeypatch):
    for provider in ai.AUTO_PROVIDER_ORDER:
        monkeypatch.setenv(ai._AI_PROVIDERS[provider]["env_var"], SECRET)

    def respond(url, **kwargs):
        request = httpx.Request("POST", url, headers=kwargs["headers"])
        return httpx.Response(401, request=request, text=PRIVATE_TEXT + SECRET)

    monkeypatch.setattr(ai.httpx, "post", respond)
    summary, used, notes = ai.generate_summary(
        provider="auto", repo_full_name="fixture/repo", repo_description="Fictional fixture"
    )
    assert summary is None and used is None and len(notes) == 4
    for provider, note in zip(ai.AUTO_PROVIDER_ORDER, notes):
        assert note.startswith(provider + " failed:")
        assert "HTTP 401" in note
        assert SECRET not in note and PRIVATE_TEXT not in note and "https://" not in note
