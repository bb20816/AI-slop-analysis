import altair as alt
import pandas as pd
import streamlit as st

import analysis

# ── 맨 위 그래프의 제목과 부제목: 아래 두 값을 원하는 문구로 고치세요 ──────────────
SLOP_TITLE = "플랫폼별 AI slop 콘텐츠 비율 추이"
SLOP_SUBTITLE = "여기에 설명을 입력하세요. (streamlit_app.py 위쪽의 SLOP_SUBTITLE을 고치면 바뀝니다.)"

# Steam과 Mastodon은 세로축을 넓게 고정한다. Bluesky는 값의 범위가 훨씬 커서 자동으로 둔다.
FIXED_Y_RANGE = {"Steam": [0, 300], "Mastodon": [0, 300]}

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

    line = (
        alt.Chart(lines)
        .mark_line(strokeWidth=1.5, point=alt.OverlayMarkDef(size=18))
        .encode(
            x=x,
            y=alt.Y("AI slop 비율(%):Q", title=y_title, scale=scale),
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
    return (line + average).properties(height=340)


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
    "**전체 기간에서는 그런 경향이 보이지만, 비교 기간을 바꾸면 사라지거나 뒤집히므로 "
    "비례 관계를 입증한 결과는 아닙니다.**"
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
st.caption(
    "굵은 직선이 추세선입니다. Steam과 Mastodon의 세로축은 0~300으로 고정했고 Bluesky는 범위가 "
    "다르므로, 기울기는 선의 모양이 아니라 각 그래프 위의 '연 %' 숫자로 비교하세요."
)

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

st.subheader("계산 기준과 한계")
st.markdown(
    "- **단위 맞추기:** 각 사이트의 활성화도를 선택한 기간의 자기 평균으로 나눠 평균을 100으로 "
    "맞춘 뒤 직선 추세를 구합니다. 기울기는 1년에 평균의 몇 %씩 변하는지를 뜻합니다.\n"
    "- **Bluesky:** 이용자 수 데이터는 기간이 너무 짧아, 게시물에 얼마나 긍정적으로 반응하는지를 보는 "
    "`좋아요 / 게시물 수^1.3`을 썼습니다. 앞뒤 평균으로 대체한 `a` 표시 값 65일과 2025년 4월 22일 "
    "보정값을 포함합니다.\n"
    "- **Mastodon:** CSV의 `activeness` 열을 그대로 썼습니다.\n"
    "- **Steam:** 활성화도 열이 없어 `in-game / users²`를 하루 평균으로 계산했습니다. "
    "2026년 1월 15일은 앞뒤 평균으로 보정한 값입니다.\n"
    "- **지표 차이:** 사이트마다 계산식이 달라 단위를 맞춰도 완전히 같은 것을 재는 것은 아닙니다.\n"
    "- **분모의 영향:** 이용자 수나 게시물 수의 제곱으로 나누면 규모가 커지기만 해도 활성화도가 "
    "떨어지므로, 기울기가 AI slop이 아니라 성장 속도를 반영할 수 있습니다.\n"
    "- **Bluesky 전체 기간 추세선 (참고용):** 2023~2024년의 초반 급락을 포함해 계산한 값입니다. 이 시기가 "
    "AI slop이 늘어나기 시작한 시기와 비슷하다고 보아 포함했지만, AI slop 수집 이전이라 데이터로 확인한 "
    "것은 아닙니다. 기울기가 연 -100%를 넘고 추세선이 0 아래로 내려갈 만큼 직선이 잘 맞지 않으므로, "
    "이 기울기는 참고용으로만 봐 주세요."
)
