from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable
from urllib.parse import urljoin

import requests
import streamlit as st
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, storage


LIST_URL = "https://news.rthk.hk/rthk/ch/latest-news/world-news.htm"
LIST_AJAX_URL = (
    "https://news.rthk.hk/rthk/webpageCache/services/loadModNewsShowSp2List.php"
)
LIST_AJAX_PARAMS = {
    "lang": "zh-TW",
    "cat": "4",  # 国际
    "newsCount": 60,
    "dayShiftMode": "1",
    "archive_date": "",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


@dataclass
class ArticleLink:
    title: str
    url: str
    time_text: str | None = None


def fetch_html(url: str, params: dict | None = None) -> str:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def normalize_url(href: str) -> str:
    return urljoin(LIST_URL, href)


def parse_list(html: str) -> list[ArticleLink]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[ArticleLink] = []

    top_container = soup.select_one(".catTopNewsContainer")
    if top_container:
        top_link = top_container.select_one("a[href]")
        top_title = top_container.select_one(".catTopNewsTitleText a")
        top_time = top_container.select_one(".catTopTime")
        if top_link and top_title:
            results.append(
                ArticleLink(
                    title=top_title.get_text(strip=True),
                    url=normalize_url(top_link["href"]),
                    time_text=top_time.get_text(strip=True) if top_time else None,
                )
            )

    for link in soup.select(".ns2-title a[href]"):
        title = link.get_text(strip=True)
        url = normalize_url(link["href"])
        time_text = None
        inner = link.find_parent(class_="ns2-inner")
        if inner:
            time_el = inner.select_one(".ns2-created")
            if time_el:
                time_text = time_el.get_text(strip=True)
        results.append(ArticleLink(title=title, url=url, time_text=time_text))

    return dedupe_by_url(results)


def dedupe_by_url(items: Iterable[ArticleLink]) -> list[ArticleLink]:
    seen: set[str] = set()
    results: list[ArticleLink] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        results.append(item)
    return results


def parse_detail(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("h2.itemTitle")
    body_el = soup.select_one(".itemFullText")
    title = title_el.get_text(strip=True) if title_el else None

    body = None
    if body_el:
        for br in body_el.find_all("br"):
            br.replace_with("\n")
        raw = body_el.get_text("\n")
        body = "\n".join(line.strip() for line in raw.splitlines() if line.strip())

    return {"title": title, "body": body}


def article_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def build_payload(items: Iterable[ArticleLink]) -> list[dict[str, str | None]]:
    payload: list[dict[str, str | None]] = []
    for item in items:
        detail_html = fetch_html(item.url)
        detail = parse_detail(detail_html)
        payload.append(
            {
                "id": article_id(item.url),
                "title": detail["title"] or item.title,
                "body": detail["body"] or "",
                "url": item.url,
                "time_text": item.time_text,
            }
        )
    return payload


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


def upload_json_to_storage(articles: list[dict[str, str | None]]) -> str:
    bucket = get_storage_bucket()
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": articles,
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    object_name = "rthk/world/top10.json"
    blob = bucket.blob(object_name)
    blob.upload_from_string(content, content_type="application/json; charset=utf-8")
    return object_name


def main() -> None:
    st.set_page_config(page_title="RTHK 国际新闻 - 手动更新", layout="wide")
    st.title("RTHK 国际新闻手动更新")
    st.caption("手动抓取最新 10 条国际新闻，并写入 Firebase。")

    with st.expander("抓取参数", expanded=False):
        max_items = st.number_input("抓取数量", min_value=1, max_value=30, value=10)
        show_bodies = st.checkbox("预览包含正文", value=False)

    if st.button("开始手动更新", type="primary"):
        with st.spinner("正在抓取列表..."):
            list_html = fetch_html(LIST_AJAX_URL, params=LIST_AJAX_PARAMS)
            links = parse_list(list_html)
            top_items = links[: int(max_items)]

        with st.spinner("正在抓取正文并上传 Storage..."):
            payload = build_payload(top_items)
            object_name = upload_json_to_storage(payload)

        st.success(f"已更新 {len(payload)} 条新闻到 Storage：{object_name}")
        st.subheader("预览")
        for item in payload:
            st.markdown(f"**{item['title']}**")
            st.write(item["url"])
            if show_bodies:
                st.write(item["body"] or "(正文为空)")
            st.divider()


if __name__ == "__main__":
    main()
