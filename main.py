import re
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="전국 고령화·학생 인구 지도",
    layout="wide"
)

st.title("🗺️ 전국 고령화·학생 인구 지도")
st.caption("시군구별 고령화율(65세 이상)과 만 16~19세 인구 비율")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():
    return pd.read_csv(
        POP_URL,
        compression="gzip",
        dtype={"코드": str}
    )


@st.cache_data(show_spinner="지도 경계를 불러오는 중입니다...")
def load_geojson():
    return requests.get(GEO_URL, timeout=30).json()


df = load_population()
geojson = load_geojson()

latest_year = int(df["연도"].max())
df = df[df["연도"] == latest_year].copy()

total_cols = [c for c in df.columns if c.startswith("계_")]


def age_of(col):
    m = re.match(r"계_(\d+)세", col)
    return int(m.group(1)) if m else None


elderly_cols = [
    c for c in total_cols
    if age_of(c) is not None and age_of(c) >= 65
]

df["전체인구"] = df[total_cols].sum(axis=1)
df["고령인구"] = df[elderly_cols].sum(axis=1)

student_cols = [
    "계_16세",
    "계_17세",
    "계_18세",
    "계_19세"
]

df["학생인구"] = df[student_cols].sum(axis=1)

df["시군구코드"] = df["코드"].str[:5]

grouped = (
    df.groupby("시군구코드")[
        ["전체인구", "고령인구", "학생인구"]
    ]
    .sum()
    .reset_index()
)

grouped["고령화율"] = (
    grouped["고령인구"]
    / grouped["전체인구"]
    * 100
)

grouped["학생비율"] = (
    grouped["학생인구"]
    / grouped["전체인구"]
    * 100
)

names = pd.DataFrame([
    {
        "시군구코드": str(f["properties"]["코드"]),
        "시군구": f["properties"]["시군구"],
        "시도": f["properties"]["시도"]
    }
    for f in geojson["features"]
])

merged = grouped.merge(
    names,
    on="시군구코드",
    how="left"
)

fig = go.Figure()

fig.add_trace(
    go.Choropleth(
        geojson=geojson,
        locations=merged["시군구코드"],
        z=merged["고령화율"],
        featureidkey="properties.코드",
        colorscale="Oranges",
        marker_line_width=0.5,
        colorbar_title="고령화율(%)",
        customdata=merged[
            ["시도", "시군구", "고령화율", "학생비율"]
        ],
        hovertemplate=
        "<b>%{customdata[1]}</b><br>"
        "시도: %{customdata[0]}<br>"
        "고령화율: %{customdata[2]:.1f}%<br>"
        "학생비율: %{customdata[3]:.1f}%<extra></extra>"
    )
)

fig.add_trace(
    go.Choropleth(
        geojson=geojson,
        locations=merged["시군구코드"],
        z=merged["학생비율"],
        featureidkey="properties.코드",
        colorscale="Blues",
        opacity=0.45,
        marker_line_width=0,
        hoverinfo="skip",
        showscale=False
    )
)

fig.update_geos(
    fitbounds="locations",
    visible=False
)

fig.update_layout(
    title=f"{latest_year}년 시군구별 고령화율 + 학생비율",
    height=800,
    margin=dict(l=0, r=0, t=50, b=0)
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🔴 고령화율 TOP 10")

    st.dataframe(
        merged.nlargest(10, "고령화율")[
            ["시도", "시군구", "고령화율"]
        ].round(2),
        hide_index=True,
        use_container_width=True
    )

with col2:
    st.subheader("🔵 학생비율 TOP 10")

    st.dataframe(
        merged.nlargest(10, "학생비율")[
            ["시도", "시군구", "학생비율"]
        ].round(2),
        hide_index=True,
        use_container_width=True
    )
