import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Indie 작가 대시보드",
    layout="wide"
)

st.markdown("""
<style>

/* multiselect 선택 태그 기본 스타일 */
span[data-baseweb="tag"] {
    color: white !important;
    font-weight: 600;
}

/* 승인 */
span[data-baseweb="tag"]:nth-child(1) {
    background-color: #22c55e !important;
}

/* 임시 승인 */
span[data-baseweb="tag"]:nth-child(2) {
    background-color: #f59e0b !important;
}

/* 반려 */
span[data-baseweb="tag"]:nth-child(3) {
    background-color: #ef4444 !important;
}

</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Indie 작가 대시보드", layout="wide")

REQUIRED_COLUMNS = ["상태", "회원번호", "닉네임", "일시", "입금 방법", "반려 사유", "비고"]


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # 필요한 컬럼 없으면 생성
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[REQUIRED_COLUMNS].copy()

    # 문자열 정리
    for col in ["상태", "회원번호", "닉네임", "입금 방법", "반려 사유", "비고"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 날짜 변환
    df["일시"] = pd.to_datetime(df["일시"], errors="coerce")

    return df


st.title("Indie 작가 대시보드")

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1Gkp8cbJjASfyvwK1DX2R8owplbeFi1dSdL2xD6SY2Bo/edit?gid=0#gid=0")
worksheet = sheet.sheet1

data = worksheet.get_all_records()
df = pd.DataFrame(data)
df = normalize_dataframe(df)

# 상태 표준화
df["상태"] = df["상태"].replace({
    "승인 ": "승인",
    " 임시 승인": "임시 승인",
    "반려 ": "반려"
})

# -----------------------
# KPI
# -----------------------
total_count = len(df)
approved_count = (df["상태"] == "승인").sum()
temp_approved_count = (df["상태"] == "임시 승인").sum()
rejected_count = (df["상태"] == "반려").sum()

approval_rate = ((approved_count + temp_approved_count) / total_count * 100) if total_count > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("총 기록 수", total_count)
c2.metric("승인", approved_count)
c3.metric("임시 승인", temp_approved_count)
c4.metric("반려", rejected_count)

st.metric("통과율(승인+임시승인)", f"{approval_rate:.1f}%")

st.divider()

# -----------------------
# 필터
# -----------------------
f1, f2, f3 = st.columns([2, 2, 2])

with f1:
    keyword = st.text_input("회원번호 / 닉네임 검색", "")

with f2:
    status_filter = st.multiselect(
        "상태 필터",
        options=["승인", "임시 승인", "반려"],
        default=["승인", "임시 승인", "반려"]
    )

with f3:
    if df["일시"].notna().sum() > 0:
        min_date = df["일시"].min().date()
        max_date = df["일시"].max().date()
        date_range = st.date_input(
            "날짜 범위",
            value=(min_date, max_date)
        )
    else:
        date_range = None

filtered_df = df.copy()

if keyword:
    filtered_df = filtered_df[
        filtered_df["회원번호"].str.contains(keyword, na=False) |
        filtered_df["닉네임"].str.contains(keyword, na=False)
    ]

filtered_df = filtered_df[filtered_df["상태"].isin(status_filter)]

if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[
        filtered_df["일시"].notna() &
        (filtered_df["일시"].dt.date >= start_date) &
        (filtered_df["일시"].dt.date <= end_date)
    ]

# -----------------------
# 차트
# -----------------------
g1, g2 = st.columns(2)

with g1:
    st.subheader("날짜별 처리 건수")

    trend_source = filtered_df.dropna(subset=["일시"]).copy()
    if len(trend_source) > 0:
        trend_source["날짜"] = trend_source["일시"].dt.date
        trend_df = (
            trend_source.groupby("날짜")
            .size()
            .reset_index(name="건수")
            .sort_values("날짜")
        )

        fig_trend = px.line(
    trend_df,
    x="날짜",
    y="건수",
    markers=True,
    color_discrete_sequence=["#60a5fa"]
)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.caption("표시할 날짜 데이터가 없습니다.")

with g2:
    st.subheader("반려 사유 분포")

    reject_df = filtered_df[filtered_df["상태"] == "반려"].copy()
    reject_df["반려 사유"] = reject_df["반려 사유"].replace("", "미입력")

    if len(reject_df) > 0:
        reason_df = (
            reject_df.groupby("반려 사유")
            .size()
            .reset_index(name="건수")
            .sort_values("건수", ascending=False)
        )
        fig_reason = px.bar(
    reason_df,
    x="반려 사유",
    y="건수",
    color_discrete_sequence=["#60a5fa"]
)
        st.plotly_chart(fig_reason, use_container_width=True)
    else:
        st.caption("반려 데이터가 없습니다.")

st.divider()

# -----------------------
# 상태 분포
# -----------------------
st.subheader("상태 분포")

status_df = (
    filtered_df.groupby("상태")
    .size()
    .reset_index(name="건수")
    .sort_values("건수", ascending=False)
)

if len(status_df) > 0:
    fig_status = px.pie(
        status_df,
        names="상태",
        values="건수",
        color="상태",
        color_discrete_map={
            "승인": "#22c55e",
            "임시 승인": "#f59e0b",
            "반려": "#ef4444"
        }
    )

    st.plotly_chart(fig_status, use_container_width=True)

else:
    st.caption("표시할 데이터가 없습니다.")
    
st.divider()

# -----------------------
# 회원별 요약
# -----------------------
st.subheader("회원별 요약")

member_summary = (
    filtered_df.groupby(["회원번호", "닉네임"])
    .agg(
        총기록수=("상태", "count"),
        승인수=("상태", lambda x: (x == "승인").sum()),
        임시승인수=("상태", lambda x: (x == "임시 승인").sum()),
        반려수=("상태", lambda x: (x == "반려").sum()),
    )
    .reset_index()
    .sort_values(["총기록수", "회원번호"], ascending=[False, True])
)

st.dataframe(member_summary, use_container_width=True)

st.divider()

# -----------------------
# 원본 기록 보기
# -----------------------
st.subheader("원본 기록")

display_df = filtered_df.copy()
display_df["일시"] = display_df["일시"].dt.strftime("%Y-%m-%d %H:%M:%S")
st.dataframe(display_df, use_container_width=True)

st.divider()

# -----------------------
# 특정 회원 상세 이력
# -----------------------
st.subheader("특정 회원 상세 이력")

target_member = st.text_input("회원번호로 상세 조회")

if target_member:
    member_df = df[df["회원번호"] == target_member].copy()

    if len(member_df) == 0:
        st.warning("해당 회원번호 기록이 없습니다.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 기록", len(member_df))
        m2.metric("승인", (member_df["상태"] == "승인").sum())
        m3.metric("임시 승인", (member_df["상태"] == "임시 승인").sum())
        m4.metric("반려", (member_df["상태"] == "반려").sum())

        member_df["일시"] = member_df["일시"].dt.strftime("%Y-%m-%d %H:%M:%S")
        st.dataframe(member_df, use_container_width=True)
