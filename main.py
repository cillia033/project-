
import json
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ============================================================
# 전국 시군구 고령화율 지도
# ============================================================

st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    layout="wide"
)

st.title("🧓 전국 시군구 고령화 지도")
st.caption("시군구별 65세 이상 인구 비율(가장 최신 연도 기준)")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


# ============================================================
# 데이터 읽기
# ============================================================

@st.cache_data
def load_population():
    # 코드는 반드시 문자열로 읽기
    df = pd.read_csv(
        POP_URL,
        compression="gzip",
        dtype={"코드": str}
    )
    return df


@st.cache_data
def load_geojson():
    r = requests.get(GEO_URL, timeout=30)
    r.raise_for_status()
    return r.json()


# ============================================================
# 최신 연도 시군구별 고령화율 계산
# ============================================================

def make_sigungu_aging(df):

    latest_year = df["연도"].max()

    latest = df[df["연도"] == latest_year].copy()

    # 읍면동 코드 → 시군구 코드(앞 5자리)
    latest["시군구코드"] = latest["코드"].str[:5]

    # 전체 인구 열
    total_cols = [
        c for c in latest.columns
        if c.startswith("계_")
    ]

    # 65세 이상 인구 열
    elderly_cols = []

    for col in total_cols:

        age_text = col.replace("계_", "")

        if age_text == "100세 이상":
            elderly_cols.append(col)
            continue

        try:
            age = int(age_text.replace("세", ""))
            if age >= 65:
                elderly_cols.append(col)
        except:
            pass

    latest["전체인구"] = latest[total_cols].sum(axis=1)
    latest["고령인구"] = latest[elderly_cols].sum(axis=1)

    sigungu = (
        latest.groupby("시군구코드", as_index=False)
        .agg(
            전체인구=("전체인구", "sum"),
            고령인구=("고령인구", "sum")
        )
    )

    sigungu["고령화율"] = (
        sigungu["고령인구"]
        / sigungu["전체인구"]
        * 100
    )

    return sigungu, latest_year


# ============================================================
# 단계 구분
# ============================================================

def classify(rate):

    if rate < 19:
        return "19% 미만"

    elif rate < 23:
        return "19~23%"

    elif rate < 28:
        return "23~28%"

    elif rate < 38:
        return "28~38%"

    else:
        return "38% 이상"


# ============================================================
# 실행
# ============================================================

pop_df = load_population()
geojson = load_geojson()

sigungu_df, latest_year = make_sigungu_aging(pop_df)

# 지도용 데이터
map_df = sigungu_df.copy()
map_df["단계"] = map_df["고령화율"].apply(classify)

# GeoJSON 속성 정보 추출
geo_info = pd.DataFrame([
    {
        "시군구코드": f["properties"]["코드"],
        "시군구": f["properties"]["시군구"],
        "시도": f["properties"]["시도"]
    }
    for f in geojson["features"]
])

map_df = map_df.merge(
    geo_info,
    on="시군구코드",
    how="left"
)

st.subheader(f"📅 기준 연도: {latest_year}")

# ============================================================
# 5단계 색상
# ============================================================

category_order = [
    "19% 미만",
    "19~23%",
    "23~28%",
    "28~38%",
    "38% 이상"
]

color_map = {
    "19% 미만": "#edf8fb",
    "19~23%": "#b2e2e2",
    "23~28%": "#66c2a4",
    "28~38%": "#2ca25f",
    "38% 이상": "#006d2c"
}

fig = go.Figure()

for cat in category_order:

    subset = map_df[map_df["단계"] == cat]

    if len(subset) == 0:
        continue

    fig.add_trace(
        go.Choroplethmapbox(
            geojson=geojson,
            locations=subset["시군구코드"],
            z=np.ones(len(subset)),
            featureidkey="properties.코드",
            colorscale=[
                [0, color_map[cat]],
                [1, color_map[cat]]
            ],
            showscale=False,
            marker_line_width=0.5,
            marker_line_color="white",
            name=cat,
            hovertemplate=
            "<b>%{customdata[0]}</b><br>"
            "시도: %{customdata[1]}<br>"
            "고령화율: %{customdata[2]:.1f}%<extra></extra>",
            customdata=np.column_stack([
                subset["시군구"],
                subset["시도"],
                subset["고령화율"]
            ])
        )
    )

fig.update_layout(
    mapbox=dict(
        style="white-bg",
        center=dict(lat=36.3, lon=127.8),
        zoom=5.7
    ),
    margin=dict(l=0, r=0, t=0, b=0),
    legend=dict(
        title="고령화율 구간",
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0
    ),
    height=700
)

st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 상위 10 / 하위 10
# ============================================================

st.markdown("---")

top10 = (
    map_df[
        ["시도", "시군구", "고령화율"]
    ]
    .sort_values("고령화율", ascending=False)
    .head(10)
    .copy()
)

bottom10 = (
    map_df[
        ["시도", "시군구", "고령화율"]
    ]
    .sort_values("고령화율", ascending=True)
    .head(10)
    .copy()
)

top10["고령화율"] = top10["고령화율"].round(1)
bottom10["고령화율"] = bottom10["고령화율"].round(1)

col1, col2 = st.columns(2)

with col1:
    st.subheader("🔺 고령화율 높은 지역 TOP 10")
    st.dataframe(
        top10,
        hide_index=True,
        use_container_width=True
    )

with col2:
    st.subheader("🔻 고령화율 낮은 지역 TOP 10")
    st.dataframe(
        bottom10,
        hide_index=True,
        use_container_width=True
    )
