from __future__ import annotations

from datetime import datetime
import json

import streamlit as st

from utils.database_utils import load_database, merge_articles, save_database
from utils.gmail_utils import get_credentials, load_client_config, send_message
from utils.scraper_utils import build_payload, fetch_list_links


def _build_email_body(items: list[dict[str, str | None]]) -> str:
    lines = [f"本次共 {len(items)} 条国际新闻：", ""]
    for idx, item in enumerate(items, 1):
        title = item.get("title") or "(标题为空)"
        lines.append(f"{idx}. {title}")
        if item.get("time_text"):
            lines.append(f"时间：{item['time_text']}")
        if item.get("url"):
            lines.append(item["url"])
        body = item.get("body")
        if body:
            lines.append(body)
        lines.append("")
    return "\n".join(lines).strip()


def _get_gmail_client_config() -> dict | None:
    if "gmail_oauth" in st.secrets:
        return load_client_config(st.secrets["gmail_oauth"])
    if "gmail" in st.secrets:
        gmail_section = dict(st.secrets["gmail"])
        if "client_config" in gmail_section:
            return load_client_config(gmail_section["client_config"])
    return None


def _render_email_panel() -> None:
    st.subheader("邮件发送")
    st.caption("手动发送未标记为 emailed 的新闻。")

    if "world_email_panel_open" not in st.session_state:
        st.session_state["world_email_panel_open"] = False

    if st.button("准备email", key="world_prepare_email"):
        st.session_state["world_email_panel_open"] = not st.session_state[
            "world_email_panel_open"
        ]

    if not st.session_state["world_email_panel_open"]:
        return

    database = load_database()
    articles = database.get("articles", [])
    unsent = [item for item in articles if not item.get("emailed")]
    unsent_count = len(unsent)

    col_left, col_right = st.columns([3, 1])
    with col_left:
        with st.expander(f"未发送的新闻：{unsent_count} 条", expanded=False):
            if unsent:
                for item in unsent:
                    st.markdown(f"- {item.get('title') or '(标题为空)'}")
            else:
                st.caption("暂无未发送新闻。")

    with col_right:
        to_email = st.text_input("收件人邮箱", key="world_email_to")
        send_disabled = not unsent or not to_email
        if st.button("发送邮件", key="world_send_email", disabled=send_disabled):
            client_config = _get_gmail_client_config()
            if not client_config:
                st.error("未找到 Gmail OAuth 配置，请先配置 st.secrets。")
                return
            token_path = st.secrets.get("gmail_token_path", "token.json")
            if not str(token_path).strip():
                token_path = None
            token_object_name = st.secrets.get("gmail_token_object")
            token_payload = None
            token_raw = st.secrets.get("gmail_token_json")
            if token_raw:
                token_payload = json.loads(token_raw) if isinstance(token_raw, str) else dict(token_raw)
            allow_oauth = bool(st.secrets.get("gmail_allow_oauth", True))
            subject = f"RTHK 国际新闻 {datetime.now().strftime('%Y-%m-%d')}"
            body = _build_email_body(unsent)
            try:
                credentials = get_credentials(
                    client_config,
                    token_path=token_path,
                    token_object_name=token_object_name,
                    token_payload=token_payload,
                    allow_oauth=allow_oauth,
                )
                send_message(credentials, to_email, subject, body)
            except Exception as exc:  # pragma: no cover - UI feedback
                st.error(f"发送失败：{exc}")
                return

            for item in unsent:
                item["emailed"] = True
            database["articles"] = articles
            save_database(database)
            st.success(f"已发送 {unsent_count} 条新闻，并更新 emailed 标记。")


def render_international_news() -> None:
    st.subheader("国际新闻")
    st.caption("手动抓取国际新闻，并与数据库比对更新。")

    with st.expander("抓取参数", expanded=False):
        max_items = st.number_input(
            "抓取数量",
            min_value=1,
            max_value=60,
            value=10,
            step=1,
            key="world_max_items",
        )
        show_bodies = st.checkbox("预览包含正文", value=False, key="world_show_bodies")

    if st.button("开始手动更新", type="primary", key="world_manual_update"):
        with st.spinner("正在抓取列表..."):
            links = fetch_list_links()
            top_items = links[: int(max_items)]

        with st.spinner("正在抓取正文并比对数据库..."):
            payload = build_payload(top_items)
            database = load_database()
            merged, created = merge_articles(
                database.get("articles", []),
                payload,
                scraped_by="manual",
            )
            database["articles"] = merged
            save_database(database)

        st.success(f"数据库已更新，新增 {len(created)} 条新闻。")
        st.caption(f"当前数据库总量：{len(merged)} 条")

        if created:
            st.subheader("新增新闻预览")
            for item in created:
                st.markdown(f"**{item['title']}**")
                st.write(item["url"])
                if show_bodies:
                    st.write(item["body"] or "(正文为空)")
                st.divider()

    st.divider()
    _render_email_panel()
