import streamlit as st
import pandas as pd
from pathlib import Path
import altair as alt

st.set_page_config(
    page_title="여행 데이터",
    page_icon="📊"
)

# =========================
# UI 스타일
# =========================

st.markdown("""
<style>

.main-title {
    font-size: 2.3rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
}

.subtitle {
    color: #6b7280;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

.section-title {
    font-size: 1.35rem;
    font-weight: 700;
    margin-top: 1.8rem;
    margin-bottom: 0.8rem;
}

.card {
    padding: 1.2rem;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.top-card {
    padding: 1.2rem;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    background: white;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.top-rank {
    font-size: 1rem;
    font-weight: 700;
}

.top-region {
    font-size: 1.4rem;
    font-weight: 800;
    margin-top: 0.4rem;
}

.top-value {
    color: #6b7280;
    margin-top: 0.3rem;
}

</style>
""", unsafe_allow_html=True)


st.markdown(
    '<div class="main-title">📊 여행 데이터 분석</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    '한국관광공사 데이터를 기반으로 여행 지역의 방문 현황을 분석합니다.'
    '</div>',
    unsafe_allow_html=True
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# 2026년 분석용 데이터 불러오기
data_path = DATA_DIR / "관광공사_지역별_방문자수_2026.csv"

df = pd.read_csv(data_path)

df["기준일"] = pd.to_datetime(
    df["기준일"]
)
# =========================
# 데이터 요약
# =========================
with st.container(border=True):
    st.markdown(
        '<div class="section-title">📌 데이터 요약</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.metric(
                "지역 수",
                f"{df['지역'].nunique()}개"
            )

    with col2:
        with st.container(border=True):
            st.metric(
                "총 방문자 수",
                f"{df['방문자수'].sum():,}명"
            )

    with col3:
        with st.container(border=True):
            st.metric(
                "평균 방문자 수",
                f"{df['방문자수'].mean():,.0f}명"
            )

# =========================
# 지역별 방문자 수 + TOP 3
# =========================

col1, col2 = st.columns([1.5, 1])

with col1:

    # =========================
    # 지역별 방문자 수
    # =========================
    with st.container(border=True):
        st.markdown(
            '<div class="section-title">🗺️ 지역별 방문자 수</div>',
            unsafe_allow_html=True
        )

        region_df = (
            df.groupby("지역", as_index=False)["방문자수"]
            .sum()
            .sort_values("방문자수", ascending=False)
        )

        region_chart = (
            alt.Chart(region_df)
            .mark_bar(
                size=28,
                cornerRadiusTopRight=6,
                cornerRadiusBottomRight=6
            )
            .encode(
                y=alt.Y(
                    "지역:N",
                    sort="-x",
                    title=None
                ),
                x=alt.X(
                    "방문자수:Q",
                    title="누적 방문자 수"
                ),
                tooltip=[
                    alt.Tooltip(
                        "지역:N",
                        title="지역"
                    ),
                    alt.Tooltip(
                        "방문자수:Q",
                        title="방문자 수",
                        format=",.0f"
                    )
                ]
            )
            .properties(
                height=500
            )
        )

        st.altair_chart(
            region_chart,
            use_container_width=True
        )

with col2:

    # =========================
    # TOP 3 여행 지역
    # =========================
    with st.container(border=True):
        st.subheader("🏆 인기 여행 지역 TOP 3")

        top3_df = (
            df.groupby("지역", as_index=False)["방문자수"]
            .sum()
            .sort_values("방문자수", ascending=False)
            .head(3)
        )

        medals = ["🥇", "🥈", "🥉"]

        for (_, row), medal in zip(
            top3_df.iterrows(),
            medals
        ):  
            st.divider()
            st.metric(
                f"{medal} {row['지역']}",
                f"{row['방문자수']:,.0f}명"
            )

            st.write("")

st.markdown(
    '<div class="section-title">📋 원본 데이터</div>',
    unsafe_allow_html=True
)

with st.expander("📂 전체 데이터 보기"):

    st.dataframe(
        df,
        hide_index=True,
        width="stretch"
    )
# =========================
# CSV 다운로드
# =========================
st.markdown(
    '<div class="section-title">📥 데이터 다운로드</div>',
    unsafe_allow_html=True
)

st.caption(
    "분석에 사용된 2026년 관광 데이터를 CSV 파일로 저장할 수 있습니다."
)

csv = df.to_csv(
    index=False,
    encoding="utf-8-sig"
)

st.download_button(
    "📥 여행 데이터 CSV 다운로드",
    data=csv,
    file_name="여행데이터.csv",
    mime="text/csv",
    type="primary"
)

# =========================
# 전체 지역 순위
# =========================

st.markdown(
    '<div class="section-title">🏆 전체 지역 순위</div>',
    unsafe_allow_html=True
)

ranking_df = (
    df.groupby("지역", as_index=False)["방문자수"]
      .sum()
      .sort_values("방문자수", ascending=False)
      .reset_index(drop=True)
)

ranking_df.insert(
    0,
    "순위",
    range(1, len(ranking_df) + 1)
)

ranking_df["방문자수"] = (
    ranking_df["방문자수"]
    .round()
    .astype(int)
)

ranking_df = ranking_df[
    ["순위", "지역", "방문자수"]
]

st.dataframe(
    ranking_df,
    hide_index=True,
    width="stretch"
)
# =========================
# 지역별 데이터 분석
# =========================

st.markdown(
    '<div class="section-title">🗺️ 지역별 데이터 분석</div>',
    unsafe_allow_html=True
)

st.caption(
    "관심 있는 지역을 선택하여 방문자 수와 전체 순위를 비교해보세요."
)

region_list = (
    df["지역"]
    .dropna()
    .unique()
    .tolist()
)

selected_regions = st.multiselect(
    "🔎 비교할 지역을 선택하세요.",
    region_list,
    default=region_list[:2],
    max_selections=4
)

# =========================
# 선택 지역 정보
# =========================

if selected_regions:

    selected_df = (
        df[df["지역"].isin(selected_regions)]
        .groupby("지역", as_index=False)["방문자수"]
        .sum()
    )

    # =========================
    # 전체 지역 순위 계산
    # =========================

    ranking_df = (
        df.groupby("지역", as_index=False)["방문자수"]
        .sum()
        .sort_values("방문자수", ascending=False)
        .reset_index(drop=True)
    )

    ranking_df["순위"] = ranking_df.index + 1

    # =========================
    # 선택 지역 순위
    # =========================
    with st.container(border=True):
        st.markdown(
            '<div class="section-title">🏆 선택 지역 순위</div>',
            unsafe_allow_html=True
        )

        selected_ranking_df = ranking_df[
            ranking_df["지역"].isin(selected_regions)
        ]

        cols = st.columns(len(selected_ranking_df))

        for col, (_, row) in zip(
            cols,
            selected_ranking_df.iterrows()
        ):
            with col:
                with st.container(border=True):
                    st.write(f"### {row['지역']}")

                    st.metric(
                        "🏆 전체 순위",
                        f"{row['순위']}위"
                    )

                    st.metric(
                        "👥 방문자 수",
                        f"{row['방문자수']:,}명"
                    )

    # =========================
    # 방문자 수 비교 그래프
    # =========================

    st.subheader("📈 방문자 수 비교")

    st.bar_chart(
        selected_df.set_index("지역")["방문자수"]
    )

else:

    st.info("비교할 지역을 하나 이상 선택해주세요.")

