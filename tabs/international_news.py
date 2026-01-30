from __future__ import annotations

import streamlit as st

from utils.database_utils import load_database, merge_articles, save_database
from utils.scraper_utils import build_payload, fetch_list_links


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
