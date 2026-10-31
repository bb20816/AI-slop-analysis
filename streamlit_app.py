from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import analysis

PERIODS: dict[str, date | None] = {
    "사이트별 전체 기간 (메인)": None,
    "2024년 9월 7일 이후": date(2024, 9, 7),
    "2026년 3월 8일 이후": date(2026, 3, 8),
}

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


def signed(value: float, digits: int = 1) -> str:
    return f"{value:+.{digits}f}"


def site_chart(name: str, result: analysis.Analysis, colors: dict) -> alt.LayerChart:
    data = result.trends[name].points.rename(
        columns={"date": "날짜", "index": "활성화도 지수", "fit": "추세선"}
    )
    x = alt.X("날짜:T", title=None, axis=alt.Axis(format="%Y-%m", tickCount=5))
    y = alt.Y("활성화도 지수:Q", title="활성화도 지수 (평균=100)")

    line = alt.Chart(data).mark_line(strokeWidth=1.5, color=colors[name]).encode(x=x, y=y)
    fit = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, color=colors["ink"])
        .encode(x=x, y="추세선:Q")
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


def slop_chart(result: analysis.Analysis, colors: dict) -> alt.LayerChart:
    data = pd.DataFrame(
        {
            "사이트": list(result.slop),
            "평균 AI slop 비율(%)": list(result.slop.values()),
            "연간 변화(%/년)": [result.slopes[name] for name in result.slop],
        }
    )
    names = list(result.slop)
    x = alt.X(
        "평균 AI slop 비율(%):Q",
        scale=alt.Scale(domain=[0, 16]),
        axis=alt.Axis(values=list(range(0, 17, 2)), grid=False),
        title="평균 AI slop 비율 (%)",
    )
    y = alt.Y("연간 변화(%/년):Q", title="활성화도 연간 변화 (%/년, 평균 대비)")

    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=colors["baseline"]).encode(y="y:Q")
    points = (
        alt.Chart(data)
        .mark_point(filled=True, size=140, opacity=1)
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "사이트:N",
                scale=alt.Scale(domain=names, range=[colors[n] for n in names]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                "사이트:N",
                alt.Tooltip("평균 AI slop 비율(%):Q", format=".2f"),
                alt.Tooltip("연간 변화(%/년):Q", format="+.1f"),
            ],
        )
    )
    labels = (
        alt.Chart(data)
        .mark_text(align="left", dx=10, color=colors["ink"], fontSize=13)
        .encode(x=x, y=y, text="사이트:N")
    )
    return (zero + points + labels).properties(height=340)


def summary_table(sites: dict) -> pd.DataFrame:
    rows = []
    for label, start in PERIODS.items():
        result = analysis.analyze(sites, start)
        rows.append(
            {
                "비교 기간": label,
                **{f"{n} (%/년)": signed(result.slopes[n]) for n in result.slopes},
                "하락폭-AI slop 상관계수": f"{result.correlation:+.2f}",
            }
        )
    return pd.DataFrame(rows)


st.set_page_config(page_title="AI Slop Analysis", layout="wide")
st.title("AI Slop Analysis")
st.markdown(
    "AI slop 비율이 높은 사이트일수록 활성화도가 빠르게 떨어지는지 살펴봅니다. "
    "**전체 기간에서는 그런 경향이 보이지만, 비교 기간을 바꾸면 사라지거나 뒤집히므로 "
    "비례 관계를 입증한 결과는 아닙니다.**"
)

colors = DARK if st.context.theme.type == "dark" else LIGHT
sites = load_sites()

period = st.radio("비교 기간", list(PERIODS), horizontal=True)
result = analysis.analyze(sites, PERIODS[period])

st.subheader("사이트별 활성화도 추세")
for column, name in zip(st.columns(3), result.trends):
    with column:
        st.markdown(
            f"**{name}**  \n연 {signed(result.slopes[name])}% · AI slop {result.slop[name]:.2f}%"
        )
        st.altair_chart(site_chart(name, result, colors), width="stretch")
st.caption(
    "그래프마다 시간 범위와 세로축 범위가 다릅니다. 굵은 직선이 추세선이고, "
    "기울기는 각 그래프 위의 '연 %' 숫자로 비교하세요."
)

st.subheader("추세 기울기와 AI slop 비율")
st.markdown(
    f"선택한 기간에서 하락폭과 AI slop 비율의 상관계수는 **{result.correlation:+.2f}**입니다. "
    "사이트가 3개뿐이라 통계적 근거로 쓰기에는 부족합니다."
)
st.altair_chart(slop_chart(result, colors), width="stretch")

st.subheader("세 기간 비교")
st.dataframe(summary_table(sites), hide_index=True, width="stretch")
st.markdown(
    "- **전체 기간:** 상관계수는 높지만 Bluesky의 큰 하락 하나에 크게 좌우됩니다. "
    "Steam과 Mastodon만 보면 AI slop 비율이 더 높은 Steam의 하락폭이 더 작습니다.\n"
    "- **2024년 9월 7일 이후:** Bluesky의 이상치 표시가 끝난 다음 날부터입니다. "
    "관계가 반대로 나타납니다.\n"
    "- **2026년 3월 8일 이후:** AI slop 데이터가 있는 기간에 가장 가깝고, "
    "세 사이트 모두 활성화도가 올랐습니다. 약 7개월뿐이고 Mastodon은 월별 데이터 7개입니다."
)

st.subheader("계산 기준과 한계")
st.markdown(
    "- **단위 맞추기:** 각 사이트의 활성화도를 선택한 기간의 자기 평균으로 나눠 평균을 100으로 "
    "맞춘 뒤 직선 추세를 구합니다. 기울기는 1년에 평균의 몇 %씩 변하는지를 뜻합니다.\n"
    "- **Bluesky:** CSV의 활성화도 값(`좋아요 / 게시물 수²`)을 썼고, `a`로 표시된 이상치 65일은 뺐습니다.\n"
    "- **Mastodon:** CSV의 `activeness` 열을 그대로 썼습니다.\n"
    "- **Steam:** 활성화도 열이 없어 `게임 중 / 접속자²`로 계산했습니다. 머리글이 없어 "
    "두 숫자 열을 접속자와 게임 중으로 추정했고, 하루 평균으로 맞췄습니다.\n"
    "- **지표 차이:** 사이트마다 계산식이 달라 단위를 맞춰도 완전히 같은 것을 재는 것은 아닙니다.\n"
    "- **분모의 영향:** 이용자 수나 게시물 수의 제곱으로 나누면 규모가 커지기만 해도 활성화도가 "
    "떨어지므로, 기울기가 AI slop이 아니라 성장 속도를 반영할 수 있습니다.\n"
    "- **기간 차이:** AI slop 비율은 2026년 3~4월부터의 약 7개월치인데, 활성화도는 그보다 훨씬 "
    "이전부터의 데이터입니다."
)
