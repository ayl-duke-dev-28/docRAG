import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauthlib.oauth2 import OAuth2Error


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"
GOOGLE_DOC_EXPORT_MIME_TYPE = "text/plain"


class GoogleDriveError(RuntimeError):
    """A user-actionable Google Drive integration failure."""


@dataclass(frozen=True)
class GoogleDriveDocument:
    id: str
    name: str
    modified_time: str = ""
    web_view_link: str = ""

    def as_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "modified_time": self.modified_time,
            "web_view_link": self.web_view_link,
        }


@dataclass(frozen=True)
class GoogleDriveExport:
    document: GoogleDriveDocument
    text: str


class OAuthStateStore:
    """Tracks short-lived, one-time OAuth state values for CSRF protection."""

    def __init__(
        self,
        ttl_seconds: int = 600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._pending: Dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(self) -> str:
        with self._lock:
            now = self._clock()
            self._pending = {
                state: expires_at
                for state, expires_at in self._pending.items()
                if expires_at > now
            }
            state = secrets.token_urlsafe(32)
            self._pending[state] = now + self._ttl_seconds
            return state

    def consume(self, state: str) -> None:
        with self._lock:
            expires_at = self._pending.pop(state, None)
            if expires_at is None or expires_at <= self._clock():
                raise GoogleDriveError("Invalid or expired Google OAuth state.")


class CredentialsStore:
    """Persists OAuth credentials outside the source tree."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> Credentials:
        if not self.exists():
            raise GoogleDriveError("Google Drive is not connected.")
        try:
            return Credentials.from_authorized_user_file(
                str(self.path),
                scopes=[DRIVE_READONLY_SCOPE],
            )
        except (OSError, ValueError) as exc:
            raise GoogleDriveError(
                "Stored Google Drive credentials are invalid; reconnect Drive."
            ) from exc

    def save(self, credentials: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(credentials.to_json())
        temporary.chmod(0o600)
        os.replace(temporary, self.path)
        self.path.chmod(0o600)

    def delete(self) -> None:
        if self.path.exists():
            self.path.unlink()


class GoogleDriveConnector:
    """OAuth and read-only Google Docs access behind a testable adapter."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        credentials_store: CredentialsStore,
        state_store: Optional[OAuthStateStore] = None,
        service_builder: Callable[..., Any] = build,
        refresh_request_factory: Callable[[], Any] = Request,
    ) -> None:
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.redirect_uri = redirect_uri.strip()
        self.credentials_store = credentials_store
        self.state_store = state_store or OAuthStateStore()
        self._service_builder = service_builder
        self._refresh_request_factory = refresh_request_factory

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def status(self) -> Dict[str, bool]:
        connected = False
        if self.configured and self.credentials_store.exists():
            try:
                self.credentials_store.load()
                connected = True
            except GoogleDriveError:
                connected = False
        return {
            "configured": self.configured,
            "connected": connected,
        }

    def start_authorization(self) -> str:
        self._require_configured()
        state = self.state_store.issue()
        flow = self._new_flow(state)
        authorization_url, returned_state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        if returned_state != state:
            raise GoogleDriveError("Google OAuth did not preserve request state.")
        return str(authorization_url)

    def finish_authorization(self, *, code: str, state: str) -> None:
        self._require_configured()
        if not code.strip():
            raise GoogleDriveError("Google OAuth returned no authorization code.")
        self.state_store.consume(state)
        flow = self._new_flow(state)
        try:
            flow.fetch_token(code=code)
        except OAuth2Error as exc:
            raise GoogleDriveError(
                f"Google OAuth token exchange failed: {exc}"
            ) from exc
        self.credentials_store.save(flow.credentials)

    def disconnect(self) -> None:
        self.credentials_store.delete()

    def list_documents(self) -> List[GoogleDriveDocument]:
        service = self._drive_service()
        documents: List[GoogleDriveDocument] = []
        page_token: Optional[str] = None
        try:
            while True:
                payload = (
                    service.files()
                    .list(
                        q=(
                            f"mimeType='{GOOGLE_DOC_MIME_TYPE}' "
                            "and trashed=false"
                        ),
                        spaces="drive",
                        orderBy="modifiedTime desc",
                        pageSize=100,
                        pageToken=page_token,
                        fields=(
                            "nextPageToken,"
                            "files(id,name,modifiedTime,webViewLink)"
                        ),
                    )
                    .execute()
                )
                documents.extend(
                    _document_from_payload(item)
                    for item in payload.get("files", [])
                )
                page_token = payload.get("nextPageToken")
                if not page_token:
                    return documents
        except HttpError as exc:
            raise GoogleDriveError(
                f"Google Drive document listing failed: {exc}"
            ) from exc

    def download_document(self, document_id: str) -> GoogleDriveExport:
        if not document_id.strip():
            raise GoogleDriveError("A Google Drive document id is required.")
        service = self._drive_service()
        try:
            payload = (
                service.files()
                .get(
                    fileId=document_id,
                    fields="id,name,mimeType,modifiedTime,webViewLink",
                )
                .execute()
            )
            if payload.get("mimeType") != GOOGLE_DOC_MIME_TYPE:
                raise GoogleDriveError(
                    "The selected Drive file is not a Google Doc."
                )
            exported = (
                service.files()
                .export(
                    fileId=document_id,
                    mimeType=GOOGLE_DOC_EXPORT_MIME_TYPE,
                )
                .execute()
            )
        except HttpError as exc:
            raise GoogleDriveError(
                f"Google Drive document export failed: {exc}"
            ) from exc

        text = (
            exported.decode("utf-8", errors="replace")
            if isinstance(exported, bytes)
            else str(exported)
        )
        return GoogleDriveExport(
            document=_document_from_payload(payload),
            text=text,
        )

    def _require_configured(self) -> None:
        if not self.configured:
            raise GoogleDriveError(
                "Google Drive OAuth is not configured. Set "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and "
                "GOOGLE_REDIRECT_URI."
            )

    def _new_flow(self, state: str) -> Flow:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=[DRIVE_READONLY_SCOPE],
            state=state,
        )
        flow.redirect_uri = self.redirect_uri
        return flow

    def _drive_service(self) -> Any:
        self._require_configured()
        credentials = self.credentials_store.load()
        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                raise GoogleDriveError(
                    "Google Drive authorization has expired; reconnect Drive."
                )
            try:
                credentials.refresh(self._refresh_request_factory())
            except RefreshError as exc:
                raise GoogleDriveError(
                    "Google Drive authorization could not be refreshed; "
                    "reconnect Drive."
                ) from exc
            self.credentials_store.save(credentials)
        return self._service_builder(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )


def _document_from_payload(payload: Dict[str, Any]) -> GoogleDriveDocument:
    document_id = str(payload.get("id", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not document_id or not name:
        raise GoogleDriveError(
            "Google Drive returned a document without an id or name."
        )
    return GoogleDriveDocument(
        id=document_id,
        name=name,
        modified_time=str(payload.get("modifiedTime", "")),
        web_view_link=str(payload.get("webViewLink", "")),
    )
