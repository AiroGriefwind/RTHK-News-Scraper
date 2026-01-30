from __future__ import annotations

from base64 import urlsafe_b64encode
import json
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from utils.firebase_utils import read_json_from_storage, upload_json_to_storage


GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def load_client_config(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


def get_credentials(
    client_config: dict[str, Any],
    token_path: str | None = "token.json",
    token_object_name: str | None = None,
    token_payload: dict[str, Any] | None = None,
    allow_oauth: bool = True,
) -> Credentials:
    token_file = Path(token_path) if token_path else None
    creds: Credentials | None = None

    if token_payload:
        creds = Credentials.from_authorized_user_info(token_payload, GMAIL_SCOPES)

    if token_object_name:
        stored = read_json_from_storage(token_object_name)
        if stored and not creds:
            creds = Credentials.from_authorized_user_info(stored, GMAIL_SCOPES)

    if not creds and token_file and token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if token_object_name:
            upload_json_to_storage(token_object_name, json.loads(creds.to_json()))
        elif token_file:
            token_file.write_text(creds.to_json(), encoding="utf-8")

    if not creds or not creds.valid:
        if not allow_oauth:
            raise RuntimeError(
                "缺少可用的 Gmail token，请先在本地完成 OAuth 授权，"
                "并配置 gmail_token_object 或 gmail_token_json。"
            )
        flow = InstalledAppFlow.from_client_config(client_config, GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        if token_object_name:
            upload_json_to_storage(token_object_name, json.loads(creds.to_json()))
        elif token_file:
            token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds


def build_message(to_email: str, subject: str, body: str) -> dict[str, str]:
    message = MIMEText(body, _charset="utf-8")
    message["to"] = to_email
    message["subject"] = subject
    raw = urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send_message(
    credentials: Credentials,
    to_email: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    message = build_message(to_email, subject, body)
    return service.users().messages().send(userId="me", body=message).execute()
