from __future__ import annotations

import json
from typing import Any

import firebase_admin
from firebase_admin import credentials, storage
import streamlit as st


def get_storage_bucket() -> storage.Bucket:
    if not firebase_admin._apps:
        firebase_config = dict(st.secrets["firebase"])
        private_key = firebase_config.get("private_key")
        if private_key:
            firebase_config["private_key"] = private_key.replace("\\n", "\n")
        bucket_name = st.secrets["firebase_storage"]["bucket"]
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
    return storage.bucket()


def read_json_from_storage(object_name: str) -> dict[str, Any] | None:
    bucket = get_storage_bucket()
    blob = bucket.blob(object_name)
    if not blob.exists():
        return None
    content = blob.download_as_text()
    return json.loads(content)


def upload_json_to_storage(object_name: str, payload: dict[str, Any]) -> None:
    bucket = get_storage_bucket()
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    blob = bucket.blob(object_name)
    blob.upload_from_string(content, content_type="application/json; charset=utf-8")
