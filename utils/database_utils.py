from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import random
import string
from typing import Any

from utils.firebase_utils import read_json_from_storage, upload_json_to_storage
from utils.scraper_utils import article_id


DB_OBJECT_NAME = "rthk/world/db.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_database(object_name: str = DB_OBJECT_NAME) -> dict[str, Any]:
    payload = read_json_from_storage(object_name)
    if not payload:
        return {"updated_at": None, "articles": []}
    payload.setdefault("articles", [])
    return payload


def save_database(payload: dict[str, Any], object_name: str = DB_OBJECT_NAME) -> None:
    payload["updated_at"] = _now_iso()
    upload_json_to_storage(object_name, payload)


def index_articles(articles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for item in articles:
        item_id = item.get("id")
        if item_id:
            results[item_id] = item
    return results


def merge_articles(
    existing: list[dict[str, Any]],
    new_items: list[dict[str, Any]],
    scraped_by: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now_iso = _now_iso()
    indexed = index_articles(existing)
    created: list[dict[str, Any]] = []

    for item in new_items:
        item_id = item.get("id")
        if not item_id:
            continue
        if item_id in indexed:
            stored = indexed[item_id]
            if not stored.get("title") and item.get("title"):
                stored["title"] = item["title"]
            if not stored.get("body") and item.get("body"):
                stored["body"] = item["body"]
            if not stored.get("time_text") and item.get("time_text"):
                stored["time_text"] = item["time_text"]
            continue

        new_record = {
            "id": item_id,
            "title": item.get("title") or "",
            "body": item.get("body") or "",
            "url": item.get("url") or "",
            "time_text": item.get("time_text"),
            "scraped_at": now_iso,
            "scraped_by": scraped_by,
            "emailed": False,
        }
        indexed[item_id] = new_record
        created.append(new_record)

    return list(indexed.values()), created


def clear_database() -> None:
    save_database({"updated_at": None, "articles": []})


def _random_slug(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def inject_fake_articles(
    count: int,
    scraped_by: str = "manual_test",
) -> tuple[int, int]:
    payload = load_database()
    articles = payload.get("articles", [])
    now_iso = _now_iso()

    for idx in range(count):
        slug = f"{_random_slug()}-{idx}"
        url = f"https://example.com/fake/{slug}"
        item_id = article_id(url)
        articles.append(
            {
                "id": item_id,
                "title": f"测试新闻 {slug}",
                "body": "这是用于测试的虚假内容。",
                "url": url,
                "time_text": None,
                "scraped_at": now_iso,
                "scraped_by": scraped_by,
                "emailed": False,
            }
        )

    payload["articles"] = articles
    save_database(payload)
    return count, len(articles)


def backup_database(
    payload: dict[str, Any],
    backup_dir: str = "backups",
) -> str:
    os.makedirs(backup_dir, exist_ok=True)
    date_part = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_part}.json"
    path = os.path.join(backup_dir, filename)
    if os.path.exists(path):
        time_part = datetime.now().strftime("%H%M%S")
        path = os.path.join(backup_dir, f"{date_part}_{time_part}.json")

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    return path
