from __future__ import annotations

from typing import Any

import httpx
import pytest

from agent.utils import github


class _Recorder:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(
            {
                "url": str(request.url),
                "method": request.method,
                "auth": request.headers.get("Authorization"),
            }
        )
        return self._responses.pop(0)


def _make_client(responses: list[httpx.Response]) -> tuple[_Recorder, Any]:
    recorder = _Recorder(responses)
    transport = httpx.MockTransport(recorder.handler)
    original = httpx.AsyncClient

    class _PatchedAsyncClient(original):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    return recorder, _PatchedAsyncClient


@pytest.mark.asyncio
async def test_create_github_pr_uses_user_token_first(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder, client_cls = _make_client(
        [
            httpx.Response(
                201,
                json={"html_url": "https://github.com/o/r/pull/1", "number": 1},
            )
        ]
    )
    monkeypatch.setattr(httpx, "AsyncClient", client_cls)

    pr_url, pr_number, existing = await github.create_github_pr(
        repo_owner="o",
        repo_name="r",
        github_token="user-token",
        title="t",
        head_branch="head",
        base_branch="main",
        body="b",
        fallback_token="install-token",
    )

    assert pr_url == "https://github.com/o/r/pull/1"
    assert pr_number == 1
    assert existing is False
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["auth"] == "Bearer user-token"


@pytest.mark.asyncio
async def test_create_github_pr_falls_back_to_installation_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder, client_cls = _make_client(
        [
            httpx.Response(404, json={"message": "Not Found"}),
            httpx.Response(
                201,
                json={"html_url": "https://github.com/o/r/pull/2", "number": 2},
            ),
        ]
    )
    monkeypatch.setattr(httpx, "AsyncClient", client_cls)

    pr_url, pr_number, existing = await github.create_github_pr(
        repo_owner="o",
        repo_name="r",
        github_token="user-token",
        title="t",
        head_branch="head",
        base_branch="main",
        body="b",
        fallback_token="install-token",
    )

    assert pr_url == "https://github.com/o/r/pull/2"
    assert pr_number == 2
    assert existing is False
    assert len(recorder.calls) == 2
    assert recorder.calls[0]["auth"] == "Bearer user-token"
    assert recorder.calls[1]["auth"] == "Bearer install-token"


@pytest.mark.asyncio
async def test_create_github_pr_returns_existing_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder, client_cls = _make_client(
        [
            httpx.Response(422, json={"message": "A pull request already exists"}),
            httpx.Response(
                200,
                json=[{"html_url": "https://github.com/o/r/pull/3", "number": 3}],
            ),
        ]
    )
    monkeypatch.setattr(httpx, "AsyncClient", client_cls)

    pr_url, pr_number, existing = await github.create_github_pr(
        repo_owner="o",
        repo_name="r",
        github_token="user-token",
        title="t",
        head_branch="head",
        base_branch="main",
        body="b",
        fallback_token="install-token",
    )

    assert pr_url == "https://github.com/o/r/pull/3"
    assert pr_number == 3
    assert existing is True
    assert len(recorder.calls) == 2
    assert all(c["auth"] == "Bearer user-token" for c in recorder.calls)
