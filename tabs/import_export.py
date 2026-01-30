from __future__ import annotations

import streamlit as st

from utils.database_utils import (
    backup_database,
    clear_database,
    inject_fake_articles,
    load_database,
)


def render_import_export() -> None:
    st.subheader("导入/导出（测试）")
    st.caption("用于测试数据库备份、清空和注入假数据。")

    database = load_database()
    total_count = len(database.get("articles", []))
    st.metric("当前数据库条数", total_count)

    if st.button("备份数据库", key="backup_db"):
        object_name = backup_database(database)
        st.success(f"已备份数据库到 Storage：{object_name}")

    if st.button("清空数据库", key="clear_db"):
        clear_database()
        st.success("数据库已清空。")

    fake_count = st.number_input(
        "注入假数据数量",
        min_value=1,
        max_value=500,
        value=20,
        step=1,
        key="fake_count",
    )
    if st.button("注入假数据", key="inject_fake"):
        added, total = inject_fake_articles(int(fake_count))
        st.success(f"已注入 {added} 条假数据，当前总量 {total} 条。")
