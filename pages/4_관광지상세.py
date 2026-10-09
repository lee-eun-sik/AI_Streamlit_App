import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="관광지 상세",
    page_icon="📍"
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

data_path = DATA_DIR / "관광공사_지역별_방문자수_2026.csv"

travel_df = pd.read_csv(data_path)

travel_df["기준일"] = pd.to_datetime(
    travel_df["기준일"]
)

if "selected_region" not in st.session_state:
    st.warning("먼저 여행지 랭킹에서 지역을 선택해주세요.")
    st.stop()

region = st.session_state.selected_region

region_summary = (
    travel_df.groupby("지역", as_index=False)["방문자수"]
    .sum()
    .sort_values("방문자수", ascending=False)
    .reset_index(drop=True)
)

region_summary["순위"] = region_summary.index + 1

selected = region_summary[
    region_summary["지역"] == region
].iloc[0]

rank = selected["순위"]
visitors = selected["방문자수"]

st.title(f"📍 {region} 여행 정보")

st.caption(
    "한국관광공사 실제 데이터를 기반으로 해당 지역의 방문자 정보를 제공합니다."
)

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "🏆 전국 순위",
        f"{rank}위"
    )

with col2:
    st.metric(
        "👥 누적 방문자 수",
        f"{visitors:,.0f}명"
    )

st.markdown("## 📊 방문자 추이")

region_trend = (
    travel_df[
        travel_df["지역"] == region
    ]
    .groupby("기준일", as_index=False)["방문자수"]
    .sum()
    .sort_values("기준일")
)

st.line_chart(
    region_trend.set_index("기준일")["방문자수"]
)