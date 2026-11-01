import altair as alt
import pandas as pd
import streamlit as st

import analysis

# ── 맨 위 그래프의 제목과 부제목 ──────────────
SLOP_TITLE = "플랫폼별 AI slop 콘텐츠 비율 추이"
SLOP_SUBTITLE = "Bluesky > Steam > Mastodon 순으로 AI slop 비율이 높다."

# Steam과 Mastodon은 세로축을 넓게 고정한다. Bluesky는 값의 범위가 커서 자동으로 둔다.
FIXED_Y_RANGE = {"Steam": [0, 350], "Mastodon": [0, 350]}

LIGHT = {
    "Bluesky": "#2a78d6",
    "Steam": "#eb6834",
    "Mastodon": "#1baf7a",
    "ink": "#0b0b0b",
    "secondary": "#52514e",
    "baseline": "#c3c2b7",
}
DARK = {
    "Bluesky": "#3987e5",
    "Steam": "#d95926",
    "Mastodon": "#199e70",
    "ink": "#f0efec",
    "secondary": "#c3c2b7",
    "baseline": "#383835",
}


@st.cache_data
def load_sites():
    return analysis.load_sites()


@st.cache_data
def load_slop_series():
    return analysis.load_slop_series_all()


def signed(value: float, digits: int = 1) -> str:
    return f"{value:+.{digits}f}"


def site_chart(name: str, result: analysis.Analysis, colors: dict) -> alt.LayerChart:
    data = result.trends[name].points.rename(
        columns={"date": "날짜", "index": "활성화도 지수", "fit": "추세선"}
    )
    x = alt.X("날짜:T", title=None, axis=alt.Axis(format="%Y-%m", tickCount=5))
    scale = alt.Scale(domain=FIXED_Y_RANGE[name]) if name in FIXED_Y_RANGE else alt.Scale()
    y = alt.Y("활성화도 지수:Q", title="활성화도 지수 (평균=100)", scale=scale)

    line = (
        alt.Chart(data)
        .mark_line(strokeWidth=1.5, color=colors[name], clip=True)
        .encode(x=x, y=y)
    )
    fit = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, color=colors["ink"], clip=True)
        .encode(x=x, y=alt.Y("추세선:Q", scale=scale))
    )

    nearest = alt.selection_point(
        fields=["날짜"], nearest=True, on="pointerover", clear="pointerout", empty=False
    )
    hover = (
        alt.Chart(data)
        .mark_rule(color=colors["secondary"])
        .encode(
            x=x,
            opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("날짜:T", format="%Y-%m-%d"),
                alt.Tooltip("활성화도 지수:Q", format=".1f"),
                alt.Tooltip("추세선:Q", format=".1f"),
            ],
        )
        .add_params(nearest)
    )
    return (line + fit + hover).properties(height=280)


def slop_timeline_chart(series: dict[str, pd.DataFrame], colors: dict) -> alt.LayerChart:
    """플랫폼별 AI slop 비율(실선)과 전체 구간 평균(같은 색 점선)을 한 그래프에 그린다."""
    names = list(series)
    lines = pd.concat(
        [df.assign(사이트=name) for name, df in series.items()], ignore_index=True
    ).rename(columns={"date": "날짜", "ai_percentage": "AI slop 비율(%)"})
    averages = pd.DataFrame(
        {
            "사이트": names,
            "전체 구간 평균(%)": [series[name]["ai_percentage"].mean() for name in names],
        }
    )

    color = alt.Color(
        "사이트:N",
        scale=alt.Scale(domain=names, range=[colors[n] for n in names]),
        legend=alt.Legend(title=None, orient="top"),
    )
    x = alt.X("날짜:T", title=None, axis=alt.Axis(format="%Y-%m", tickCount=8))
    y_title = "AI slop 비율 (%)"
    scale = alt.Scale(domainMin=0)

    y = alt.Y("AI slop 비율(%):Q", title=y_title, scale=scale)
    line = alt.Chart(lines).mark_line(strokeWidth=1.5).encode(x=x, y=y, color=color)
    # 점은 보이지 않게(opacity=0) 두고 마우스를 올렸을 때 값만 알려 준다.
    hover = (
        alt.Chart(lines)
        .mark_point(opacity=0, size=80)
        .encode(
            x=x,
            y=y,
            color=color,
            tooltip=[
                "사이트:N",
                alt.Tooltip("날짜:T", format="%Y-%m-%d"),
                alt.Tooltip("AI slop 비율(%):Q", format=".2f"),
            ],
        )
    )
    average = (
        alt.Chart(averages)
        .mark_rule(strokeWidth=2, strokeDash=[6, 4])
        .encode(
            y=alt.Y("전체 구간 평균(%):Q", title=y_title, scale=scale),
            color=color,
            tooltip=["사이트:N", alt.Tooltip("전체 구간 평균(%):Q", format=".2f")],
        )
    )
    return (line + hover + average).properties(height=340)


def decline_chart(
    changes: dict[str, analysis.EdgeChange], slop: dict[str, float], colors: dict
) -> alt.LayerChart:
    """플랫폼마다 과거(=100)와 현재 활성화도 막대를 나란히 그리고, 위에 감소율을 적는다."""
    names = list(changes)
    labels = {name: f"{name} ({slop[name]:.2f}%)" for name in names}
    order = list(labels.values())

    rows = []
    for name in names:
        change = changes[name]
        rows.append(
            {"플랫폼": labels[name], "시점": "과거", "활성화도": analysis.INDEX_BASE, "색": colors["secondary"]}
        )
        rows.append(
            {"플랫폼": labels[name], "시점": "현재", "활성화도": change.current_index, "색": colors[name]}
        )
    data = pd.DataFrame(rows)
    drops = pd.DataFrame(
        {
            "플랫폼": order,
            "감소율": [f"{changes[name].change_pct:+.1f}%" for name in names],
            "위치": [analysis.INDEX_BASE * 1.2] * len(names),
        }
    )

    x = alt.X("플랫폼:N", sort=order, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=13))
    offset = alt.XOffset("시점:N", sort=["과거", "현재"])
    y = alt.Y(
        "활성화도:Q",
        title="활성화도 (과거 = 100)",
        scale=alt.Scale(domain=[0, analysis.INDEX_BASE * 1.3]),
    )

    bars = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=x,
            xOffset=offset,
            y=y,
            color=alt.Color("색:N", scale=None, legend=None),
            tooltip=["플랫폼:N", "시점:N", alt.Tooltip("활성화도:Q", format=".1f")],
        )
    )
    values = (
        alt.Chart(data)
        .mark_text(dy=-8, fontSize=12, color=colors["ink"])
        .encode(x=x, xOffset=offset, y=y, text=alt.Text("활성화도:Q", format=".1f"))
    )
    drop_text = (
        alt.Chart(drops)
        .mark_text(fontSize=16, fontWeight="bold", color=colors["ink"])
        .encode(x=x, y=alt.Y("위치:Q", scale=alt.Scale(domain=[0, analysis.INDEX_BASE * 1.3])), text="감소율:N")
    )
    return (bars + values + drop_text).properties(height=340)


def period_sliders(sites: dict) -> dict:
    st.sidebar.header("분석 기간")
    st.sidebar.caption("사이트별 추세 그래프와 과거 대비 현재 막대 그래프에 적용됩니다. 처음에는 전체 기간입니다.")
    ranges = {}
    for name, (df, _) in sites.items():
        first, last = df["date"].min().date(), df["date"].max().date()
        start, end = st.sidebar.slider(
            name, first, last, (first, last), format="YYYY-MM-DD", key=f"period_{name}"
        )
        rows = df["date"].between(pd.Timestamp(start), pd.Timestamp(end)).sum()
        if rows < 2:
            st.sidebar.warning(f"{name}: 선택한 기간의 데이터가 부족해 전체 기간으로 계산합니다.")
            start, end = first, last
        ranges[name] = (start, end)
    return ranges


st.set_page_config(page_title="AI Slop Analysis", layout="wide")

colors = DARK if st.context.theme.type == "dark" else LIGHT

# ── 맨 위: 플랫폼별 AI slop 비율 추이 (기간 슬라이더 없음, 항상 전체 기간) ─────────
slop_series = load_slop_series()
st.header(SLOP_TITLE)
st.markdown(SLOP_SUBTITLE)
st.altair_chart(slop_timeline_chart(slop_series, colors), width="stretch")
st.caption(
    "실선은 날짜별 AI slop 비율, 같은 색 점선은 해당 플랫폼의 전체 구간 평균입니다. "
    + " · ".join(
        f"{name} 평균 {df['ai_percentage'].mean():.2f}% "
        f"({df['date'].min():%Y-%m-%d} ~ {df['date'].max():%Y-%m-%d}, {len(df)}개)"
        for name, df in slop_series.items()
    )
)
st.divider()

st.title("AI Slop Analysis")
st.markdown(
    "AI slop 비율이 높은 사이트일수록 활성화도가 빠르게 떨어지는지 살펴봅니다. "
    "왼쪽 사이드바의 슬라이더를 이용해 기간을 조절할 수 있습니다."
)

sites = load_sites()

ranges = period_sliders(sites)
result = analysis.analyze(sites, ranges)

st.subheader("사이트별 활성화도 추세")
for column, name in zip(st.columns(3), result.trends):
    with column:
        st.markdown(
            f"**{name}**  \n연 {signed(result.slopes[name])}% · AI slop {result.slop[name]:.2f}%  \n"
            f"{ranges[name][0]} ~ {ranges[name][1]}"
        )
        st.altair_chart(site_chart(name, result, colors), width="stretch")

st.subheader("과거 대비 현재 활성화도")
changes = {name: analysis.edge_change(df, *ranges[name]) for name, (df, _) in sites.items()}
st.markdown(
    "각 플랫폼의 **과거** 활성화도를 100으로 놓았을 때 **현재** 활성화도가 얼마인지 보여줍니다. "
    f"과거는 선택한 기간의 처음 {analysis.EDGE_FRACTION:.0%}, 현재는 끝 {analysis.EDGE_FRACTION:.0%}의 "
    "평균입니다. 가로축 이름 옆 괄호는 평균 AI slop 비율입니다."
)
st.altair_chart(decline_chart(changes, result.slop, colors), width="stretch")
st.caption(
    "왼쪽 회색 막대가 과거, 오른쪽 색 막대가 현재이고 위의 %는 과거 대비 변화입니다. "
    + " · ".join(
        f"{name}: 과거·현재 각 {change.rows}개 평균 ({ranges[name][0]} ~ {ranges[name][1]})"
        for name, change in changes.items()
    )
)
st.divider()
st.markdown('<div style="height: 24px;"></div>', unsafe_allow_html=True)

st.subheader("결과 분석과 근거")
st.markdown(
    "AI slop이 늘어날수록 활성화도가 줄어듭니다.  \n"
    "중앙 일보 2026.02.09 기사  “ ‘돈’ 같지만 ‘독’이다…‘AI 쓰레기’ 단속 나선 플랫폼들”"
    "( https://www.joongang.co.kr/article/25403514 )에 따르면  \n"
    "AI slop이 플랫폼의 사용자 경험을 악화하기 때문에, AI slop과 활성화도의 상관관계는 인과관계로 해석할 수 있습다."
)
st.divider()
st.markdown('<div style="height: 24px;"></div>', unsafe_allow_html=True)

st.subheader("해결책과 제안")
st.markdown(
    "고로 플랫폼 운영자들은 스스로 유저들이 만든 AI slop 콘텐츠에 대해 경고, 차단, 또는 삭 등의 조치를 취해야 합니다.  \n"
    "실제로 음원 플랫폼 spotify는 저품질 및 스팸성 AI 생성 음원 5,000만 곡 이상을 사용자 추천(피드) 목록에서 차단했습니다.( https://www.yna.co.kr/view/AKR20261021083600009 )"
)
st.divider()
st.markdown('<div style="height: 24px;"></div>', unsafe_allow_html=True)


st.subheader("계산 기준과 한계")
st.markdown(
    "데이터의 사이사이 일부 날짜의 결측치는 표시하지 않고, 데이터가 있는 날짜만 연결하여 꺾은선그래프로 표시했습니다.  \n"
    "데이터의 이상치는 모두 전날과 다음날의 평균으로 대체했습니다.  \n"
    "- **단위 맞추기:** 각 사이트의 활성화도를 선택한 기간의 자기 평균으로 나눠 평균을 100으로 "
    "맞춘 뒤 직선 추세를 구합니다. 기울기는 1년에 평균의 몇 %씩 변하는지를 뜻합니다.  \n"
    #"- **활성화도 계산:** Mastodon: (좋아요 수)/(유저 수), Steam: (인 게임 유저 수)/(유저 수)^2, Bluesky: 이용자 수 데이터는 기간이 너무 짧아, "
    #"게시물에 얼마나 긍정적으로 반응하는지를 보는 (좋아요) / (게시물 수)^1.3을 사용"
    "- **한계:** Bluesky는 이용자수 데이터의 기간이 너무 짧아, 게시물에 얼마나 긍정적으로 반응하는지를 보는 (좋아요 수)와 (게시물 수) 데이터를 사용하여 사이트마다 완전히 같은 것을 재는 것은 아닙니다.  \n"
    "또한, AI slop 콘텐츠의 증가와 무관한 이유로 활성화도가 줄어들었을 경우 이를 감안하지 못합니다.  \n"
)
