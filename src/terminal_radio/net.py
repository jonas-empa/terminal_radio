"""Shared HTTP plumbing for station catalogs."""

from __future__ import annotations

from typing import Any

import httpx

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_TIMEOUT = 15.0


class FetchError(Exception):
    """A station catalog or stream probe could not be fetched."""


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        follow_redirects=True,
    )


async def fetch_json(client: httpx.AsyncClient, url: str, **params: str) -> Any:
    """GET ``url`` and parse the JSON body, raising :class:`FetchError`."""
    try:
        response = await client.get(url, params=params or None)
    except httpx.HTTPError as exc:
        raise FetchError(f"Network error while contacting {url}: {exc}") from exc
    if response.status_code >= 400:
        raise FetchError(f"{url}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise FetchError(f"{url}: response was not valid JSON.") from exc


async def probe_stream(client: httpx.AsyncClient, url: str) -> int | None:
    """Best-effort preflight check of a stream URL.

    Returns the final HTTP status, or ``None`` if the server could not be
    reached or rejected the HEAD method. Only clear authorization failures
    (401/403) should be treated as fatal by callers — many legacy Shoutcast
    servers answer HEAD oddly while GET streams fine.
    """
    try:
        response = await client.head(url)
        return response.status_code
    except httpx.HTTPError:
        return None


AUTH_FAILURE_STATUSES = frozenset({401, 403, 410})
