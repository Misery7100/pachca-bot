"""Integration tests for the FastAPI endpoints."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from pachca_bot.api.app import create_app


@pytest.fixture()
def _env(monkeypatch):
    monkeypatch.setenv("PACHCA_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("PACHCA_CHAT_ID", "12345")
    monkeypatch.setenv("GITHUB__WEBHOOK_SECRET", "gh-secret")
    monkeypatch.setenv("GENERIC__WEBHOOK_SECRET", "gen-secret")


@pytest.fixture()
def client(_env):
    app = create_app()
    mock_pachca = MagicMock()
    mock_pachca.send_message.return_value = {"id": 999}
    mock_pachca.get_messages.return_value = []
    mock_pachca.create_thread.return_value = {"id": 500}
    mock_pachca.post_to_thread.return_value = {"id": 501}
    mock_pachca.update_message.return_value = {"id": 999}

    with patch("pachca_bot.api.app.PachcaClient", return_value=mock_pachca):
        with TestClient(app) as tc:
            yield tc, mock_pachca


def _github_sig(body: bytes, secret: str = "gh-secret") -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class TestHealth:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestGitHubEndpoint:
    def test_release(self, client):
        tc, mock = client
        body = json.dumps(
            {
                "action": "published",
                "repository": {"full_name": "org/repo"},
                "release": {
                    "tag_name": "v1.0",
                    "name": "v1.0",
                    "body": "notes",
                    "html_url": "https://github.com/org/repo/releases/v1.0",
                    "author": {"login": "alice"},
                },
            }
        ).encode()
        resp = tc.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": _github_sig(body),
                "X-GitHub-Event": "release",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert mock.send_message.call_args[1]["display_name"] == "GitHub Bot"

    def test_invalid_signature(self, client):
        tc, _ = client
        body = b'{"action":"published"}'
        resp = tc.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "release",
            },
        )
        assert resp.status_code == 403

    def test_github_secret_not_configured(self, monkeypatch):
        monkeypatch.setenv("PACHCA_ACCESS_TOKEN", "test-token")
        monkeypatch.setenv("PACHCA_CHAT_ID", "12345")
        monkeypatch.delenv("GITHUB__WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("GENERIC__WEBHOOK_SECRET", "gen-secret")
        app = create_app()
        mock_pachca = MagicMock()
        with patch("pachca_bot.api.app.PachcaClient", return_value=mock_pachca):
            with TestClient(app) as tc:
                resp = tc.post(
                    "/webhooks/github",
                    content=b'{"action":"published","repository":{"full_name":"x"},"release":{"tag_name":"v1","name":"v1","html_url":"u","author":{"login":"a"}}}',
                    headers={"X-Hub-Signature-256": "sha256=x", "X-GitHub-Event": "release"},
                )
        assert resp.status_code == 403
        assert "webhook secret" in resp.json()["detail"].lower()

    def test_pr_opened(self, client):
        tc, mock = client
        body = json.dumps(
            {
                "action": "opened",
                "repository": {"full_name": "org/repo"},
                "pull_request": {
                    "number": 1,
                    "title": "Feat",
                    "html_url": "https://github.com/org/repo/pull/1",
                    "user": {"login": "alice"},
                    "head": {"ref": "feat"},
                    "base": {"ref": "main"},
                    "draft": False,
                },
            }
        ).encode()
        resp = tc.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": _github_sig(body),
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        mock.send_message.assert_called_once()


class TestGenericEndpoint:
    def test_alert(self, client):
        tc, mock = client
        body = json.dumps(
            {
                "event_type": "alert",
                "source": "vm-01",
                "title": "High memory",
                "severity": "warning",
            }
        ).encode()
        resp = tc.post(
            "/webhooks/generic",
            content=body,
            headers={
                "X-Authorization": "Bearer gen-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert mock.send_message.call_args[1]["display_name"] == "Events Bot"

    def test_unauthorized(self, client):
        tc, _ = client
        body = json.dumps({"event_type": "alert", "source": "x", "title": "y"}).encode()
        resp = tc.post(
            "/webhooks/generic",
            content=body,
            headers={"X-Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 403

    def test_generic_secret_not_configured(self, monkeypatch):
        monkeypatch.setenv("PACHCA_ACCESS_TOKEN", "test-token")
        monkeypatch.setenv("PACHCA_CHAT_ID", "12345")
        monkeypatch.setenv("GITHUB__WEBHOOK_SECRET", "gh-secret")
        monkeypatch.delenv("GENERIC__WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("GENERIC_WEBHOOK_SECRET", raising=False)
        app = create_app()
        mock_pachca = MagicMock()
        with patch("pachca_bot.api.app.PachcaClient", return_value=mock_pachca):
            with TestClient(app) as tc:
                resp = tc.post(
                    "/webhooks/generic",
                    content=json.dumps(
                        {"event_type": "alert", "source": "x", "title": "y"}
                    ).encode(),
                    headers={"X-Authorization": "Bearer any-token"},
                )
        assert resp.status_code == 403
        assert "webhook secret" in resp.json()["detail"].lower()

    def test_deploy_with_id(self, client):
        tc, mock = client
        body = json.dumps(
            {
                "event_type": "deploy",
                "source": "api",
                "title": "",
                "environment": "prod",
                "version": "3.0",
                "status": "started",
                "deploy_id": "dep-1",
            }
        ).encode()
        resp = tc.post(
            "/webhooks/generic",
            content=body,
            headers={
                "X-Authorization": "Bearer gen-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
