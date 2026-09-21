import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from shapely.geometry import shape

st.set_page_config(
    page_title="전국 고령화·학생 인구 지도",
    layout="wide"
)

st.title("🗺️ 전국 고령화·학생 인구 지도")
st.caption("시군구별 고령화율(65세 이상)과 만 16~19세 인구 비율")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


@st.cache_data
def load_population():
    return pd.read_csv(
        POP_URL,
        compression="gzip",
        dtype={"코드": str}
    )


@st.cache_data
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

student_cols = [
    "계_16세",
    "계_17세",
    "계_18세",
    "계_19세"
]

df["전체인구"] = df[total_cols].sum(axis=1)
df["고령인구"] = df[elderly_cols].sum(axis=1)
df["학생인구"] = df[student_cols].sum(axis=1)

df["시군구코드"] = df["코드"].str[:5]

grouped = (
    df.groupby("시군구코드")[["전체인구", "고령인구", "학생인구"]]
    .sum()
    .reset_index()
)

grouped["고령화율"] = (
    grouped["고령인구"] / grouped["전체인구"] * 100
)

grouped["학생비율"] = (
    grouped["학생인구"] / grouped["전체인구"] * 100
)

regions = []
centers = []

for feature in geojson["features"]:
    props = feature["properties"]

    code = str(props["코드"])

    geom = shape(feature["geometry"])
    centroid = geom.centroid

    regions.append(
        {
            "시군구코드": code,
            "시군구": props["시군구"],
            "시도": props["시도"]
        }
    )

    centers.append(
        {
            "시군구코드": code,
            "lon": centroid.x,
            "lat": centroid.y
        }
    )

names_df = pd.DataFrame(regions)
center_df = pd.DataFrame(centers)

merged = (
    grouped
    .merge(names_df, on="시군구코드", how="left")
    .merge(center_df, on="시군구코드", how="left")
)

bins = [0, 19, 23, 28, 38, 100]

labels = [
    "19% 미만",
    "19~23%",
    "23~28%",
    "28~38%",
    "38% 이상"
]

merged["고령화단계"] = pd.cut(
    merged["고령화율"],
    bins=bins,
    labels=labels,
    right=False
)

color_map = {
    "19% 미만": "#fee6ce",
    "19~23%": "#fdc086",
    "23~28%": "#f79646",
    "28~38%": "#e8590c",
    "38% 이상": "#a63603"
}

fig = px.choropleth(
    merged,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="고령화단계",
    category_orders={"고령화단계": labels},
    color_discrete_map=color_map,
    hover_name="시군구",
    hover_data={
        "시도": True,
        "고령화율": ":.1f",
        "학생비율": ":.1f",
        "시군구코드": False,
        "고령화단계": False
    }
)

fig.add_scattergeo(
    lon=merged["lon"],
    lat=merged["lat"],
    mode="markers",
    text=merged["시군구"],
    customdata=merged[
        [
            "시도",
            "고령화율",
            "학생비율",
            "학생인구"
        ]
    ],
    marker=dict(
        size=merged["학생비율"] * 2,
        color="blue",
        opacity=0.45,
        line=dict(width=0)
    ),
    hovertemplate=
    "<b>%{text}</b><br>"
    "시도: %{customdata[0]}<br>"
    "고령화율: %{customdata[1]:.1f}%<br>"
    "학생비율: %{customdata[2]:.1f}%<br>"
    "학생수: %{customdata[3]:,.0f}명"
    "<extra></extra>",
    showlegend=False
)

fig.update_geos(
    fitbounds="locations",
    visible=False
)

fig.update_layout(
    height=800,
    margin=dict(l=0, r=0, t=10, b=0),
    legend_title_text=f"고령화율 ({latest_year}년)"
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
