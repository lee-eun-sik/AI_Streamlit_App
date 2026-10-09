import streamlit as st
import pandas as pd

from pathlib import Path
from datetime import date

# =========================
# UI 스타일
# =========================

st.markdown("""
<style>

.main-title {
    font-size: 2.4rem;
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
    margin-top: 2rem;
    margin-bottom: 0.8rem;
}

.info-box {
    padding: 1rem 1.2rem;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    background-color: #f8fafc;
    margin-bottom: 1rem;
}

.top-card {
    padding: 1.2rem;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    background-color: white;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.top-rank {
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
}

.top-region {
    font-size: 1.35rem;
    font-weight: 800;
}

.top-value {
    color: #6b7280;
    margin-top: 0.3rem;
}

</style>
""", unsafe_allow_html=True)
# =========================
# 기본 설정
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent



DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)



st.set_page_config(
    page_title="여행지 랭킹",
    page_icon="🗺️"
)


st.markdown(
    '<div class="main-title">🗺️ 인기 여행지 랭킹</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    '한국관광공사 지역별 방문자 데이터를 기반으로 '
    '기간별 인기 지역을 확인해보세요.'
    '</div>',
    unsafe_allow_html=True
)

# =========================
# 실제 데이터 불러오기
# =========================

data_path = DATA_DIR / "관광공사_지역별_방문자수_2026.csv"

df = pd.read_csv(data_path)

df["기준일"] = pd.to_datetime(
    df["기준일"]
)

MIN_DATE = df["기준일"].min().date()
MAX_DATE = df["기준일"].max().date()

st.markdown(
    '<div class="section-title">📅 조회 기간</div>',
    unsafe_allow_html=True
)

# =========================
# 날짜 선택
# =========================

col1, col2 = st.columns(2)

with col1:

    start_date = st.date_input(
        "조회 시작일",
        value=MIN_DATE,
        min_value=MIN_DATE,
        max_value=MAX_DATE
    )

with col2:

    end_date = st.date_input(
        "조회 종료일",
        value=MAX_DATE,
        min_value=MIN_DATE,
        max_value=MAX_DATE
    )

# =========================
# 조회
# =========================

if st.button(
    "🔍 여행지 랭킹 조회",
    type="primary",
    use_container_width=True
):

    if start_date > end_date:

        st.error(
            "시작일은 종료일보다 빠르거나 같아야 합니다."
        )

    else:

        filtered_df = df[
            (df["기준일"] >= pd.Timestamp(start_date)) &
            (df["기준일"] <= pd.Timestamp(end_date))
        ].copy()

        if filtered_df.empty:

            st.warning(
                "선택한 기간에 데이터가 없습니다."
            )

        else:

            st.success(
                f"총 {len(filtered_df):,}건의 데이터를 불러왔습니다."
            )

            st.session_state.visitor_df = filtered_df

            # 지역별 누적 방문자 수
            ranking_df = (
                filtered_df
                .groupby("지역", as_index=False)["방문자수"]
                .sum()
                .sort_values(
                    "방문자수",
                    ascending=False
                )
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

            st.session_state.ranking_df = ranking_df
            st.session_state.ranking_page = 1
# =========================
# 조회 결과가 있을 때만 출력
# =========================

if "ranking_df" in st.session_state:

    ranking_df = st.session_state.ranking_df
    df = st.session_state.visitor_df
    # =========================
    # 지역 랭킹 페이지네이션
    # =========================

    PAGE_SIZE = 10
    PAGE_GROUP_SIZE = 5

    total_pages = (
        len(ranking_df) + PAGE_SIZE - 1
    ) // PAGE_SIZE

    if "ranking_page" not in st.session_state:
        st.session_state.ranking_page = 1

    current_page = st.session_state.ranking_page

    # 현재 페이지 그룹
    current_group = (
        current_page - 1
    ) // PAGE_GROUP_SIZE

    start_page = (
        current_group * PAGE_GROUP_SIZE + 1
    )

    end_page = min(
        start_page + PAGE_GROUP_SIZE - 1,
        total_pages
    )
    start_index = (
        current_page - 1
    ) * PAGE_SIZE

    end_index = start_index + PAGE_SIZE

    page_ranking_df = ranking_df.iloc[
        start_index:end_index
    ]

    st.subheader("🗺️ 지역별 방문자 랭킹")

    for _, row in page_ranking_df.iterrows():

        region = row["지역"]

        with st.container(border=True):

            col1, col2, col3, col4 = st.columns([0.7, 2, 1.5, 1])

            with col1:
                st.markdown(f"**{row['순위']}위**")

            with col2:
                st.markdown(f"### 📍 {region}")

            with col3:
                st.write(
                    f"👥 **{row['방문자수']:,}명**"
                )

            with col4:
                if st.button(
                    "📍 상세 보기",
                    key=f"detail_{region}",
                    use_container_width=True
                ):
                    st.session_state.selected_region = region
                    st.switch_page("pages/4_관광지상세.py")
    # =========================
    # 페이지 버튼
    # =========================

    cols = st.columns(7)

    # 이전 페이지 그룹
    with cols[0]:

        if st.button("<<"):

            st.session_state.ranking_page = max(
                1,
                start_page - PAGE_GROUP_SIZE
            )

            st.rerun()

    # 페이지 번호
    for i, page in enumerate(
        range(start_page, end_page + 1),
        start=1
    ):

        with cols[i]:

            if st.button(str(page)):

                st.session_state.ranking_page = page

                st.rerun()

    # 다음 페이지 그룹
    with cols[6]:

        if st.button(">>"):

            if end_page < total_pages:

                st.session_state.ranking_page = (
                    start_page + PAGE_GROUP_SIZE
                )

                st.rerun()

    # =========================
    # 인기 지역 TOP 3
    # =========================

    st.markdown(
        '<div class="section-title">🏆 인기 여행 지역 TOP 3</div>',
        unsafe_allow_html=True
    )

    top3_df = ranking_df.head(3)

    cols = st.columns(3)

    medals = ["🥇", "🥈", "🥉"]

    for col, medal, (_, row) in zip(
        cols,
        medals,
        top3_df.iterrows()
    ):
        with col:
            st.markdown(
                f"""
                <div class="top-card">
                    <div class="top-rank">{medal} {row['순위']}위</div>
                    <div class="top-region">{row['지역']}</div>
                    <div class="top-value">
                        {row['방문자수']:,}명
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    # =========================
    # 인기 지역 TOP 10
    # =========================

    st.markdown(
        '<div class="section-title">📋 전체 인기 지역 TOP 10</div>',
        unsafe_allow_html=True
    )

    st.dataframe(
        ranking_df.head(10),
        hide_index=True,
        width="stretch"
    )


    # =========================
    # 방문자 수
    # =========================

    st.markdown(
        '<div class="section-title">📊 선택 기간 누적 방문자 수</div>',
        unsafe_allow_html=True
    )

    st.bar_chart(
        ranking_df.head(10).set_index("지역")["방문자수"]
    )

    # =========================
    # 방문자 유형별 분석
    # =========================

    st.markdown(
        '<div class="section-title">👥 방문자 유형별 분석</div>',
        unsafe_allow_html=True
    )

    visitor_type_df = (
        df.groupby("방문자구분")["방문자수"]
        .sum()
        .reset_index()
    )

    visitor_type_df["방문자수"] = (
        visitor_type_df["방문자수"]
        .round()
        .astype(int)
    )

    col1, col2 = st.columns(2)

    with col1:
        st.dataframe(
            visitor_type_df,
            hide_index=True,
            width="stretch"
        )

    with col2:
        st.bar_chart(
            visitor_type_df.set_index("방문자구분")["방문자수"]
        )


    # =========================
    # 지역별 방문자 유형
    # =========================

    st.subheader("🔎 지역별 방문자 유형")

    selected_region = st.selectbox(
        "🔎 분석할 지역을 선택하세요.",
        ranking_df["지역"].tolist()
    )
    # =========================
    # 선택 지역 상세 정보
    # =========================
    selected_rank = ranking_df.loc[
        ranking_df["지역"] == selected_region,
        "순위"
    ].iloc[0]

    selected_visitors = ranking_df.loc[
        ranking_df["지역"] == selected_region,
        "방문자수"
    ].iloc[0]

    st.markdown(
        f'<div class="section-title">📍 {selected_region} 상세 분석</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "현재 순위",
            f"{selected_rank}위"
        )

    with col2:
        st.metric(
            "선택 기간 누적 방문자 수",
            f"{selected_visitors:,}명"
        )
    selected_df = df[
        df["지역"] == selected_region
    ]

    selected_type_df = (
        selected_df
        .groupby("방문자구분")["방문자수"]
        .sum()
        .reset_index()
    )

    selected_type_df["방문자수"] = (
        selected_type_df["방문자수"]
        .round()
        .astype(int)
    )

    st.dataframe(
        selected_type_df,
        hide_index=True,
        width="stretch"
    )

    st.bar_chart(
        selected_type_df.set_index("방문자구분")["방문자수"]
    )