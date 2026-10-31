"""사이트별 활성화도 추세와 평균 AI slop 비율을 비교한다.

활성화도는 사이트마다 계산식과 단위가 다르므로, 각 사이트를 자기 평균으로 나눠
평균이 100인 지수로 맞춘 뒤 추세선 기울기를 "연간 평균 대비 %"로 비교한다.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
DAYS_PER_YEAR = 365.25
INDEX_BASE = 100.0


@dataclass(frozen=True)
class Trend:
    points: pd.DataFrame  # date, index(평균=100), fit(추세선)
    slope_pct_per_year: float


@dataclass(frozen=True)
class Analysis:
    trends: dict[str, Trend]
    slopes: dict[str, float]
    slop: dict[str, float]
    correlation: float


def trend(
    df: pd.DataFrame, start: date | None = None, end: date | None = None
) -> Trend:
    """start~end 구간(양 끝 포함)만 평균=100으로 맞추고 직선 추세를 구한다."""
    if start is not None:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end is not None:
        df = df[df["date"] <= pd.Timestamp(end)]
    if len(df) < 2:
        raise ValueError("추세를 구하려면 데이터가 2개 이상 필요합니다.")
    df = df.sort_values("date")

    index = df["activeness"] / df["activeness"].mean() * INDEX_BASE
    years = (df["date"] - df["date"].iloc[0]).dt.total_seconds() / 86400 / DAYS_PER_YEAR
    slope, intercept = np.polyfit(years, index, 1)

    points = pd.DataFrame(
        {"date": df["date"], "index": index, "fit": slope * years + intercept}
    ).reset_index(drop=True)
    return Trend(points=points, slope_pct_per_year=float(slope))


def decline_slop_correlation(slopes: dict[str, float], slop: dict[str, float]) -> float:
    """하락폭(-기울기)과 AI slop 비율의 피어슨 상관계수."""
    names = list(slop)
    declines = [-slopes[name] for name in names]
    return float(np.corrcoef(declines, [slop[name] for name in names])[0, 1])


def load_bluesky(path: Path) -> pd.DataFrame:
    # 활성화도 = 좋아요 / 게시물 수². a로 표시된 행은 앞뒤 평균으로 대체한 값이므로 포함한다.
    # CSV의 활성화도 열은 좋아요·게시물을 보정한 뒤 갱신되지 않은 행이 있어 쓰지 않는다.
    raw = pd.read_csv(path, encoding="cp949", encoding_errors="replace")
    return pd.DataFrame(
        {
            "date": pd.to_datetime(raw["date"]),
            "activeness": raw["num_likes"] / raw["num_posts"] ** 2,
        }
    )


def load_mastodon(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame(
        {
            "date": pd.to_datetime(raw["month"], format="%y-%b"),
            "activeness": raw["activeness"].astype(float),
        }
    )


def load_steam(path: Path) -> pd.DataFrame:
    # 머리글이 없고, 숫자 열은 순서대로 users, in-game이다.
    # 최근 데이터만 10분 단위이므로 하루 평균으로 맞춘 뒤 in-game / users² 를 구한다.
    raw = pd.read_csv(
        path, encoding="utf-8-sig", header=None, names=["time", "users", "in_game"]
    )
    raw["date"] = pd.to_datetime(raw["time"], format="%Y-%m-%d %H:%M").dt.normalize()
    daily = raw.groupby("date", as_index=False)[["users", "in_game"]].mean()
    return pd.DataFrame(
        {"date": daily["date"], "activeness": daily["in_game"] / daily["users"] ** 2}
    )


def load_slop_average(path: Path) -> float:
    raw = pd.read_csv(path, encoding="utf-8-sig")
    return float(raw["average ai_percentage"].dropna().iloc[0])


def load_sites(data_dir: Path = DATA_DIR) -> dict[str, tuple[pd.DataFrame, float]]:
    """{사이트: (활성화도, 평균 AI slop 비율)}"""
    return {
        "Bluesky": (
            load_bluesky(data_dir / "bluesky_statistics_fixed.csv"),
            load_slop_average(data_dir / "bluesky_ai_slop.csv"),
        ),
        "Steam": (
            load_steam(data_dir / "steamdb_chart_753_fixed.csv"),
            load_slop_average(data_dir / "steam_ai_slop.csv"),
        ),
        "Mastodon": (
            load_mastodon(data_dir / "mastodon_08_users_favourites_monthly.csv"),
            load_slop_average(data_dir / "mastodon_ai_slop.csv"),
        ),
    }


def analyze(
    sites: dict[str, tuple[pd.DataFrame, float]],
    ranges: dict[str, tuple[date | None, date | None]],
) -> Analysis:
    """ranges: {사이트: (시작, 끝)}. 사이트마다 다른 기간을 쓸 수 있고, None은 제한 없음."""
    trends = {name: trend(df, *ranges[name]) for name, (df, _) in sites.items()}
    slopes = {name: t.slope_pct_per_year for name, t in trends.items()}
    slop = {name: value for name, (_, value) in sites.items()}
    return Analysis(
        trends=trends,
        slopes=slopes,
        slop=slop,
        correlation=decline_slop_correlation(slopes, slop),
    )
