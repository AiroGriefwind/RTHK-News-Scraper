from __future__ import annotations

import streamlit as st

from tabs.import_export import render_import_export
from tabs.international_news import render_international_news


def main() -> None:
    st.set_page_config(page_title="RTHK 新闻工具", layout="wide")
    st.title("RTHK 新闻工具")
    st.caption("测试阶段：数据库比对、更新与备份功能。")

    tab_world, tab_import = st.tabs(["国际新闻", "导入/导出"])
    with tab_world:
        render_international_news()
    with tab_import:
        render_import_export()


if __name__ == "__main__":
    main()
