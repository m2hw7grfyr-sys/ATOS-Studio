from __future__ import annotations

from typing import Optional

import httpx
from pydantic import ValidationError

from config.settings import get_settings
from models.schemas import AtosContentItem, AtosContentListResponse, AtosHealthResponse


class AtosClientError(Exception):
    pass


class AtosAuthError(AtosClientError):
    pass


class AtosUnavailableError(AtosClientError):
    pass


class AtosNotFoundError(AtosClientError):
    pass


class AtosResponseError(AtosClientError):
    pass


class AtosClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.atos_base_url.rstrip("/")
        self.token = settings.atos_studio_api_token
        self.timeout = settings.atos_request_timeout_seconds

    def headers(self) -> dict[str, str]:
        if not self.token or self.token == "replace-with-the-same-token":
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def request(self, method: str, path: str, params: Optional[dict] = None) -> dict:
        if not self.base_url:
            raise AtosUnavailableError("ATOS is not configured")
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.request(method, path, params=params, headers=self.headers())
        except httpx.ConnectError as exc:
            raise AtosUnavailableError("ATOS service is unreachable") from exc
        except httpx.TimeoutException as exc:
            raise AtosUnavailableError("ATOS request timed out") from exc
        except httpx.HTTPError as exc:
            raise AtosUnavailableError("ATOS request failed") from exc

        if response.status_code == 401:
            raise AtosAuthError("ATOS Studio API authentication failed")
        if response.status_code == 404:
            raise AtosNotFoundError("ATOS content item was not found")
        if response.status_code >= 400:
            raise AtosResponseError(f"ATOS returned HTTP {response.status_code}")

        payload = response.json()
        if isinstance(payload, dict) and "data" in payload:
            if payload.get("success") is False:
                raise AtosResponseError(str(payload.get("message") or "ATOS returned an error"))
            return payload["data"]
        return payload

    def health_check(self) -> AtosHealthResponse:
        try:
            return AtosHealthResponse.model_validate(self.request("GET", "/api/studio/health"))
        except ValidationError as exc:
            raise AtosResponseError("ATOS health response did not match the expected schema") from exc

    def list_content_items(self, **params) -> AtosContentListResponse:
        try:
            return AtosContentListResponse.model_validate(
                self.request("GET", "/api/studio/content-items", params=params)
            )
        except ValidationError as exc:
            raise AtosResponseError("ATOS content list response did not match the expected schema") from exc

    def get_content_item(self, source_post_id: str) -> AtosContentItem:
        try:
            return AtosContentItem.model_validate(
                self.request("GET", f"/api/studio/content-items/{source_post_id}")
            )
        except ValidationError as exc:
            raise AtosResponseError("ATOS content item response did not match the expected schema") from exc

