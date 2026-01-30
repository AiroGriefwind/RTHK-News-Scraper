from __future__ import annotations

import argparse
import json
from pathlib import Path

import tomllib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import firebase_admin
from firebase_admin import credentials as fb_credentials, storage


GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def load_secrets(path: Path) -> dict:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_client_config(secrets: dict) -> dict | None:
    if "gmail_oauth" in secrets:
        return json.loads(secrets["gmail_oauth"])
    gmail = secrets.get("gmail")
    if isinstance(gmail, dict) and "client_config" in gmail:
        return json.loads(gmail["client_config"])
    return None


def load_token_from_storage(secrets: dict) -> dict | None:
    token_object = secrets.get("gmail_token_object")
    if not token_object:
        return None
    bucket_name = secrets.get("firebase_storage", {}).get("bucket")
    if not bucket_name:
        return None
    firebase_config = secrets.get("firebase")
    if not firebase_config:
        return None

    if not firebase_admin._apps:
        config = dict(firebase_config)
        private_key = config.get("private_key")
        if private_key:
            config["private_key"] = private_key.replace("\\n", "\n")
        cred = fb_credentials.Certificate(config)
        firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})

    bucket = storage.bucket()
    blob = bucket.blob(token_object)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())


def upload_token_to_storage(secrets: dict, token_payload: dict) -> None:
    token_object = secrets.get("gmail_token_object")
    bucket_name = secrets.get("firebase_storage", {}).get("bucket")
    firebase_config = secrets.get("firebase")
    if not (token_object and bucket_name and firebase_config):
        raise RuntimeError("缺少 firebase 配置或 gmail_token_object。")

    if not firebase_admin._apps:
        config = dict(firebase_config)
        private_key = config.get("private_key")
        if private_key:
            config["private_key"] = private_key.replace("\\n", "\n")
        cred = fb_credentials.Certificate(config)
        firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})

    bucket = storage.bucket()
    blob = bucket.blob(token_object)
    blob.upload_from_string(
        json.dumps(token_payload, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )


def refresh_if_needed(creds: Credentials, secrets: dict, upload: bool) -> Credentials:
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if upload:
            upload_token_to_storage(secrets, json.loads(creds.to_json()))
    return creds


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Gmail OAuth token")
    parser.add_argument(
        "--secrets",
        default=".streamlit/secrets.toml",
        help="secrets.toml 路径",
    )
    parser.add_argument(
        "--output",
        default="token.json",
        help="token 输出路径",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="生成后上传到 Firebase Storage (需在 secrets.toml 中配置)",
    )
    args = parser.parse_args()

    secrets_path = Path(args.secrets)
    secrets = load_secrets(secrets_path)
    client_config = load_client_config(secrets)
    if not client_config:
        raise SystemExit("未找到 Gmail OAuth 配置，请检查 secrets.toml。")

    creds = None
    stored = load_token_from_storage(secrets)
    if stored:
        creds = Credentials.from_authorized_user_info(stored, GMAIL_SCOPES)
        creds = refresh_if_needed(creds, secrets, args.upload)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(client_config, GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)

    token_path = Path(args.output)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    if args.upload:
        upload_token_to_storage(secrets, json.loads(creds.to_json()))

    print(f"Token 已保存到 {token_path}")


if __name__ == "__main__":
    main()
