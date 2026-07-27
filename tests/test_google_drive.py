import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docrag.google_drive import (
    CredentialsStore,
    GoogleDriveConnector,
    GoogleDriveDocument,
    GoogleDriveError,
    GoogleDriveExport,
    OAuthStateStore,
)


def test_oauth_state_is_one_time_and_expires():
    now = [100.0]
    states = OAuthStateStore(ttl_seconds=60, clock=lambda: now[0])

    valid = states.issue()
    states.consume(valid)
    with pytest.raises(GoogleDriveError, match="Invalid or expired"):
        states.consume(valid)

    expired = states.issue()
    now[0] = 161.0
    with pytest.raises(GoogleDriveError, match="Invalid or expired"):
        states.consume(expired)


def test_connector_requires_oauth_configuration(tmp_path: Path):
    connector = GoogleDriveConnector(
        client_id="",
        client_secret="",
        redirect_uri="http://localhost/callback",
        credentials_store=CredentialsStore(tmp_path / "credentials.json"),
    )

    assert connector.status() == {"configured": False, "connected": False}
    with pytest.raises(GoogleDriveError, match="not configured"):
        connector.start_authorization()


def test_oauth_callback_validates_state_and_persists_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    credentials_path = tmp_path / "credentials.json"
    connector = GoogleDriveConnector(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost/callback",
        credentials_store=CredentialsStore(credentials_path),
    )
    flows = []

    class FakeCredentials:
        def to_json(self):
            return json.dumps(
                {
                    "token": "access-token",
                    "refresh_token": "refresh-token",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
                }
            )

    class FakeFlow:
        def __init__(self, state):
            self.state = state
            self.credentials = FakeCredentials()
            self.fetches = []

        def authorization_url(self, **kwargs):
            assert kwargs["access_type"] == "offline"
            assert kwargs["include_granted_scopes"] == "true"
            return f"https://accounts.example/authorize?state={self.state}", self.state

        def fetch_token(self, **kwargs):
            self.fetches.append(kwargs)

    def new_flow(state):
        flow = FakeFlow(state)
        flows.append(flow)
        return flow

    monkeypatch.setattr(connector, "_new_flow", new_flow)

    authorization_url = connector.start_authorization()
    state = authorization_url.rsplit("=", 1)[1]
    connector.finish_authorization(code="auth-code", state=state)

    assert flows[-1].fetches == [{"code": "auth-code"}]
    assert credentials_path.exists()
    assert credentials_path.stat().st_mode & 0o777 == 0o600
    assert connector.status() == {"configured": True, "connected": True}
    with pytest.raises(GoogleDriveError, match="Invalid or expired"):
        connector.finish_authorization(code="replay", state=state)


def test_list_documents_follows_drive_pagination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    connector = GoogleDriveConnector(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost/callback",
        credentials_store=CredentialsStore(tmp_path / "credentials.json"),
    )
    calls = []
    pages = [
        {
            "files": [
                {
                    "id": "doc-1",
                    "name": "March sync",
                    "modifiedTime": "2026-07-20T10:00:00Z",
                    "webViewLink": "https://docs.google.com/document/d/doc-1",
                }
            ],
            "nextPageToken": "next",
        },
        {
            "files": [
                {
                    "id": "doc-2",
                    "name": "Methods review",
                    "modifiedTime": "2026-07-19T10:00:00Z",
                }
            ]
        },
    ]

    class Request:
        def __init__(self, payload):
            self.payload = payload

        def execute(self):
            return self.payload

    class Files:
        def list(self, **kwargs):
            calls.append(kwargs)
            return Request(pages[len(calls) - 1])

    class Service:
        def files(self):
            return Files()

    monkeypatch.setattr(connector, "_drive_service", lambda: Service())

    documents = connector.list_documents()

    assert [document.id for document in documents] == ["doc-1", "doc-2"]
    assert calls[0]["q"] == (
        "mimeType='application/vnd.google-apps.document' and trashed=false"
    )
    assert calls[1]["pageToken"] == "next"


def test_download_document_exports_plain_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    connector = GoogleDriveConnector(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost/callback",
        credentials_store=CredentialsStore(tmp_path / "credentials.json"),
    )

    class Request:
        def __init__(self, payload):
            self.payload = payload

        def execute(self):
            return self.payload

    class Files:
        def get(self, **kwargs):
            assert kwargs == {
                "fileId": "doc-1",
                "fields": "id,name,mimeType,modifiedTime,webViewLink",
            }
            return Request(
                {
                    "id": "doc-1",
                    "name": "March / team sync",
                    "mimeType": "application/vnd.google-apps.document",
                    "modifiedTime": "2026-07-20T10:00:00Z",
                }
            )

        def export(self, **kwargs):
            assert kwargs == {"fileId": "doc-1", "mimeType": "text/plain"}
            return Request(b"Alex Liu chose curriculum learning.")

    class Service:
        def files(self):
            return Files()

    monkeypatch.setattr(connector, "_drive_service", lambda: Service())

    exported = connector.download_document("doc-1")

    assert exported.document.name == "March / team sync"
    assert exported.text == "Alex Liu chose curriculum learning."


def test_google_drive_import_endpoint_uses_the_existing_ingestion_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import app as app_module

    imported = []

    class FakeConnector:
        def download_document(self, document_id):
            assert document_id == "doc-1"
            return GoogleDriveExport(
                document=GoogleDriveDocument(id="doc-1", name="March / team sync"),
                text="Alex Liu chose curriculum learning.",
            )

    def fake_ingest(path, filename):
        imported.append((path.read_text(), filename))
        return {
            "status": "ingested",
            "document_id": 7,
            "filename": filename,
            "chunks": 1,
        }

    monkeypatch.setattr(app_module, "google_drive_connector", FakeConnector())
    monkeypatch.setattr(app_module, "ingest_file", fake_ingest)
    client = TestClient(app_module.app)

    response = client.post(
        "/api/google-drive/import",
        json={"document_ids": ["doc-1", "doc-1"]},
    )

    assert response.status_code == 200
    assert imported == [
        ("Alex Liu chose curriculum learning.", "March - team sync.md")
    ]
    assert response.json()["results"][0]["source"] == {
        "provider": "google_drive",
        "document_id": "doc-1",
    }

    too_many = client.post(
        "/api/google-drive/import",
        json={"document_ids": [f"doc-{index}" for index in range(26)]},
    )
    assert too_many.status_code == 400
    assert too_many.json()["detail"] == "Import at most 25 Google Docs at a time."


def test_google_drive_oauth_and_listing_endpoints(
    monkeypatch: pytest.MonkeyPatch,
):
    import app as app_module

    calls = []

    class FakeConnector:
        def status(self):
            return {"configured": True, "connected": False}

        def start_authorization(self):
            return "https://accounts.example/authorize"

        def finish_authorization(self, *, code, state):
            calls.append((code, state))

        def list_documents(self):
            return [
                GoogleDriveDocument(
                    id="doc-1",
                    name="March sync",
                    modified_time="2026-07-20T10:00:00Z",
                )
            ]

    monkeypatch.setattr(app_module, "google_drive_connector", FakeConnector())
    client = TestClient(app_module.app)

    assert client.get("/api/google-drive/status").json() == {
        "configured": True,
        "connected": False,
    }
    assert client.get("/api/google-drive/connect").json() == {
        "authorization_url": "https://accounts.example/authorize"
    }
    callback = client.get(
        "/api/google-drive/callback",
        params={"code": "auth-code", "state": "oauth-state"},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "/?google_drive=connected"
    assert calls == [("auth-code", "oauth-state")]
    assert client.get("/api/google-drive/documents").json() == {
        "documents": [
            {
                "id": "doc-1",
                "name": "March sync",
                "modified_time": "2026-07-20T10:00:00Z",
                "web_view_link": "",
            }
        ]
    }
