"""Google Auth фабрика для stitcher — только OAuth и Sheets readonly scope."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2.credentials import Credentials as OAuthUserCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    GoogleAuthRequest = None  # type: ignore
    OAuthUserCredentials = None  # type: ignore
    InstalledAppFlow = None  # type: ignore
    build = None  # type: ignore


class GoogleServicesFactory:
    _SCOPES: Tuple[str, ...] = (
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    )

    def __init__(
        self,
        *,
        credentials_path: Path,
        token_path: Path,
    ) -> None:
        self._cached_credentials: Optional[Any] = None
        self._credentials_path = credentials_path
        self._token_path = token_path

    def create_sheets_service(self) -> Any:
        """Создать и вернуть Google Sheets API сервис."""
        if build is None:
            raise RuntimeError(
                "Google API client недоступен (googleapiclient не установлен)."
            )
        creds: Any = self._get_credentials()
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    def _get_credentials(self) -> Any:
        if self._cached_credentials is not None:
            return self._cached_credentials
        self._cached_credentials = _create_oauth_user_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=self._SCOPES,
        )
        return self._cached_credentials


def _create_oauth_user_credentials(
    *,
    credentials_path: Path,
    token_path: Path,
    scopes: Sequence[str],
) -> Any:
    if OAuthUserCredentials is None or GoogleAuthRequest is None or InstalledAppFlow is None:
        raise RuntimeError("google-auth и google-auth-oauthlib не установлены.")
    if not credentials_path.exists() or not credentials_path.is_file():
        raise RuntimeError(
            f"OAuth credentials файл не найден: {credentials_path!r}. "
            "Скачайте Desktop OAuth client из Google Cloud Console."
        )

    creds: Optional[Any] = None
    if token_path.exists() and token_path.is_file():
        try:
            creds = OAuthUserCredentials.from_authorized_user_file(
                str(token_path), scopes=list(scopes)
            )
        except Exception:
            creds = None

    if creds and getattr(creds, "valid", False):
        return creds

    if creds and getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
        try:
            creds.refresh(GoogleAuthRequest())
            token_path.write_text(str(creds.to_json()), encoding="utf-8")
            return creds
        except Exception:
            creds = None

    try:
        flow: Any = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), scopes=list(scopes)
        )
        try:
            creds = flow.run_local_server(port=0)
        except Exception:
            run_console = getattr(flow, "run_console", None)
            if run_console is None:
                raise RuntimeError(
                    "OAuth local server flow завершился ошибкой, console fallback недоступен."
                )
            creds = run_console()
        if creds is None:
            raise RuntimeError("OAuth flow вернул пустой объект credentials.")
        token_path.write_text(str(creds.to_json()), encoding="utf-8")
        return creds
    except Exception as error:
        raise RuntimeError(
            "Не удалось создать OAuth token. "
            f"credentials={credentials_path!r} token={token_path!r}. "
            "Проверьте OAuth Desktop credentials и браузерный flow."
        ) from error
